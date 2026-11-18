"""Knowledge-base source K over the CRAG movie and open knowledge graphs."""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MOCK = ROOT / "mock_api"
os.environ.setdefault("KG_BASE_DIRECTORY", str(MOCK / "cragkg"))
sys.path.insert(0, str(MOCK))

from wk import crag, probes
from wk.baseline_agent import run_extractive
from wk.contract import Evidence, Question, SourceRun

DOMAINS = ("movie", "open")
MAX_NGRAM = 8
MAX_ENTITIES = 3
MAX_LIST = 40
MIN_SINGLE_TOKEN = 4
RELATION_RECALL = 0.5

MOVIE_RELATIONS = {
    "release_date": ("release", "released", "when", "year", "date", "came"),
    "budget": ("budget", "cost"),
    "revenue": ("revenue", "gross", "grossed", "box", "earn", "earned", "made"),
    "rating": ("rating", "rated", "score"),
    "genres": ("genre", "genres", "kind", "type"),
    "cast": ("cast", "star", "stars", "starred", "actor", "actress", "played",
             "plays", "role", "character"),
    "crew": ("direct", "directed", "director", "producer", "produced",
             "writer", "wrote", "written", "composer", "crew"),
    "original_language": ("language",),
}
PERSON_RELATIONS = {
    "birthday": ("born", "birthday", "birth", "age", "old"),
    "acted_movies": ("acted", "act", "star", "starred", "appear", "appeared",
                     "movies", "films", "role"),
    "directed_movies": ("direct", "directed", "director"),
}
AWARD_CUES = ("oscar", "oscars", "academy", "award", "awards", "nominated",
              "nomination", "won", "win")
_YEAR = re.compile(r"\b(19[3-9]\d|20[0-4]\d)\b")


def spell_date(value: Any) -> str:
    try:
        d = datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return str(value)
    return f"{value} {d.day} {d:%B} {d.year} {d:%B} {d.day} {d.year}"


def spell_money(value: Any) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if n >= 1e9:
        return f"{int(n)} {n / 1e9:.2f} billion {n / 1e9:.1f} billion"
    if n >= 1e6:
        return f"{int(n)} {n / 1e6:.1f} million {round(n / 1e6)} million"
    return str(int(n))


class KnowledgeBase:
    def __init__(self) -> None:
        from cragapi.movie import MovieKG
        from cragapi.open import OpenKG
        self.movie = MovieKG()
        self.open = OpenKG()
        self.movies = self.movie._movie_db
        self.persons = self.movie._person_db
        self.years = self.movie._year_db
        self.coverage = {"movie": self._coverage(self.movies, MOVIE_RELATIONS),
                         "person": self._coverage(self.persons,
                                                  PERSON_RELATIONS)}

    @staticmethod
    def _coverage(db: dict, relations: dict) -> dict[str, float]:
        sample = list(db.values())[:5000]
        return {rel: sum(bool(rec.get(rel)) for rec in sample) / len(sample)
                for rel in relations}

    def link(self, q: Question) -> list[tuple[str, str]]:
        tokens = self.movie._normalize(q.text).split()
        tables = [("open", self.open.key_map)] if q.domain == "open" else [
            ("movie", self.movies), ("person", self.persons)]
        found: list[tuple[str, str]] = []
        used = [False] * len(tokens)
        for size in range(min(MAX_NGRAM, len(tokens)), 0, -1):
            for i in range(len(tokens) - size + 1):
                if any(used[i:i + size]):
                    continue
                name = " ".join(tokens[i:i + size])
                if size == 1 and (name in crag.STOPWORDS
                                  or len(name) < MIN_SINGLE_TOKEN):
                    continue
                for kind, table in tables:
                    if name in table:
                        found.append((kind, name))
                        used[i:i + size] = [True] * size
                        break
        return found[:MAX_ENTITIES]

    def movie_facts(self, rec: dict) -> list[str]:
        t = rec.get("title") or rec.get("original_title") or ""
        out = []
        if rec.get("release_date"):
            out.append(f"{t} release date {spell_date(rec['release_date'])}.")
        for key in ("budget", "revenue"):
            if rec.get(key):
                out.append(f"{t} {key} {spell_money(rec[key])} dollars.")
        if rec.get("rating"):
            out.append(f"{t} rating {rec['rating']} out of ten.")
        if rec.get("original_language"):
            out.append(f"{t} original language {rec['original_language']}.")
        if rec.get("genres"):
            names = ", ".join(g.get("name", "") for g in rec["genres"])
            out.append(f"{t} genres {names}.")
        for c in (rec.get("cast") or [])[:MAX_LIST]:
            out.append(f"{t} cast {c.get('name')} plays {c.get('character')}.")
        for c in (rec.get("crew") or [])[:MAX_LIST]:
            out.append(f"{t} {c.get('job')} is {c.get('name')}.")
        return out

    def person_facts(self, rec: dict) -> list[str]:
        n = rec.get("name", "")
        out = []
        if rec.get("birthday"):
            out.append(f"{n} was born on {spell_date(rec['birthday'])}.")
        for rel, verb in (("acted_movies", "acted in"),
                          ("directed_movies", "directed")):
            for mid in (rec.get(rel) or [])[:MAX_LIST]:
                m = self.movie.get_movie_info_by_id(mid) or {}
                if m.get("title"):
                    out.append(f"{n} {verb} {m['title']} released "
                               f"{spell_date(m.get('release_date', ''))}.")
        return out

    def year_facts(self, year: str) -> list[str]:
        out = []
        for a in (self.years.get(year, {}).get("oscar_awards") or []):
            won = "won" if a.get("winner") else "was nominated for"
            out.append(f"In {year} {a.get('name')} {won} the Oscar for "
                       f"{a.get('category')} for the film {a.get('film')}.")
        return out


def _relation(q: Question, kind: str) -> str | None:
    words = set(crag._tokens(q.text))
    table = MOVIE_RELATIONS if kind == "movie" else PERSON_RELATIONS
    for rel, cues in table.items():
        if words & set(cues):
            return rel
    return None


class KBSource:
    name = "K"

    def __init__(self, kb: KnowledgeBase | None = None) -> None:
        self.kb = kb or KnowledgeBase()

    def retrieve(self, q: Question) -> Evidence:
        kb = self.kb
        links = kb.link(q)
        items: list[dict[str, Any]] = []
        present, coverage, etype = 0.0, 0.0, ""
        for kind, name in links:
            etype = etype or kind
            if kind == "open":
                for key in kb.open.key_map[name][:2]:
                    body = kb.open.get_entity(key)
                    text = body if isinstance(body, str) else json.dumps(body)
                    items.append({"entity": name, "text": text[:20000]})
                asked = [t for t in crag._tokens(q.text)
                         if t not in crag.STOPWORDS and t not in name.split()]
                seen = set(crag._tokens(" ".join(i["text"] for i in items)))
                hit = sum(t in seen for t in asked) / max(len(asked), 1)
                present = max(present, float(hit >= RELATION_RECALL))
                coverage = max(coverage, 1.0)
                continue
            rec = (kb.movies if kind == "movie" else kb.persons)[name]
            facts = (kb.movie_facts(rec) if kind == "movie"
                     else kb.person_facts(rec))
            items += [{"entity": name, "text": f} for f in facts]
            rel = _relation(q, kind)
            if rel:
                present = max(present, float(bool(rec.get(rel))))
                coverage = max(coverage, kb.coverage[kind][rel])
        words = set(crag._tokens(q.text))
        if q.domain == "movie" and words & set(AWARD_CUES):
            for year in _YEAR.findall(q.text)[:2]:
                facts = kb.year_facts(year)
                items += [{"entity": year, "text": f} for f in facts]
                if facts:
                    present, coverage = 1.0, 1.0
                    etype = etype or "year"
        return Evidence(source="K", items=items, meta={
            "entity_resolved": float(bool(items)),
            "relation_present": present,
            "node_degree": float(len(items)),
            "entity_type": etype,
            "type_coverage": coverage,
            "n_entities": float(len(links)),
            "link_tokens": float(max((len(n.split()) for _, n in links),
                                     default=0))})

    def probe(self, q: Question, ev: Evidence) -> dict[str, float]:
        out = probes.probe_kb(q, ev)
        out["n_entities"] = ev.meta["n_entities"]
        out["link_tokens"] = ev.meta["link_tokens"]
        return out

    def contains_answer(self, q: Question, ev: Evidence) -> bool:
        haystack = crag._tokens(" ".join(i["text"] for i in ev.items))
        if not haystack:
            return False
        item = crag.RAW_ITEMS.get(q.qid, {})
        golds = [q.answer, *crag._alt_answers(item)]
        return any(crag.answer_present(g, q.text, haystack) for g in golds)

    def run(self, q: Question, ev: Evidence, n: int = 10) -> SourceRun:
        return replace(run_extractive(q, ev, n=n), source="K")
