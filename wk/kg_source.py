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

DOMAINS = ("movie", "open", "music", "finance", "sports")
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
ARTIST_RELATIONS = {
    "birth_date": ("born", "birth", "birthday", "age", "old"),
    "country": ("country", "from", "origin", "nationality", "where"),
    "members": ("member", "members", "lineup", "band", "who"),
    "end_date": ("disband", "disbanded", "split", "ended", "broke"),
}
PLAYER_RELATIONS = {
    "birthdate": ("born", "birth", "birthday", "age", "old"),
    "school": ("school", "college", "university", "attend", "played"),
    "country": ("country", "from", "nationality", "where"),
    "height": ("tall", "height"),
    "position": ("position", "play", "plays"),
    "draft_year": ("draft", "drafted", "pick", "round", "selected"),
    "team_name": ("team", "plays", "played", "for"),
}
SONG_RELATIONS = {
    "author": ("who", "author", "artist", "sang", "sings", "performed",
               "wrote", "by"),
    "date": ("when", "released", "release", "year", "date"),
    "country": ("country", "where", "origin"),
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
        import pickle
        from cragapi.movie import MovieKG
        from cragapi.open import OpenKG
        self.movie = MovieKG()
        self.open = OpenKG()
        self.movies = self.movie._movie_db
        self.persons = self.movie._person_db
        self.years = self.movie._year_db
        music = MOCK / "cragkg" / "music"
        self.artists, self.songs, self.charts = {}, {}, {}
        if (music / "artist_dict_simplified.pickle").exists():
            raw_a = pickle.load(open(music / "artist_dict_simplified.pickle",
                                     "rb"))
            raw_s = pickle.load(open(music / "song_dict_simplified.pickle",
                                     "rb"))
            self.artists = {self.movie._normalize(k): v
                            for k, v in raw_a.items()}
            self.songs = {self.movie._normalize(k): v
                          for k, v in raw_s.items()}
            self.charts = self._charts(
                pickle.load(open(music / "rank_dict_hot100.pickle", "rb")))
        self.players = {}
        nba = MOCK / "cragkg" / "sports" / "nba.sqlite"
        if nba.exists():
            import sqlite3
            con = sqlite3.connect(f"file:{nba}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            cols = ("display_first_last, birthdate, school, country, height, "
                    "weight, position, draft_year, draft_round, draft_number, "
                    "from_year, to_year, team_name, jersey, greatest_75_flag")
            for row in con.execute(f"select {cols} from common_player_info"):
                name = row["display_first_last"]
                if name:
                    self.players[self.movie._normalize(name)] = dict(row)
            con.close()
        self.finance = None
        if (MOCK / "cragkg" / "finance" / "finance_marketcap.sqlite").exists():
            try:
                from cragapi.finance import FinanceKG
                self.finance = FinanceKG()
            except Exception:
                self.players = {}
        nba = MOCK / "cragkg" / "sports" / "nba.sqlite"
        if nba.exists():
            import sqlite3
            con = sqlite3.connect(f"file:{nba}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            cols = ("display_first_last, birthdate, school, country, height, "
                    "weight, position, draft_year, draft_round, draft_number, "
                    "from_year, to_year, team_name, jersey, greatest_75_flag")
            for row in con.execute(f"select {cols} from common_player_info"):
                name = row["display_first_last"]
                if name:
                    self.players[self.movie._normalize(name)] = dict(row)
            con.close()
        self.finance = None
        self.coverage = {"player": self._coverage(self.players,
                                                   PLAYER_RELATIONS),
                         "movie": self._coverage(self.movies, MOVIE_RELATIONS),
                         "person": self._coverage(self.persons,
                                                  PERSON_RELATIONS),
                         "artist": self._coverage(self.artists,
                                                  ARTIST_RELATIONS),
                         "song": self._coverage(self.songs, SONG_RELATIONS)}

    @staticmethod
    def _coverage(db: dict, relations: dict) -> dict[str, float]:
        sample = list(db.values())[:5000]
        if not sample:
            return {rel: 0.0 for rel in relations}
        return {rel: sum(bool(rec.get(rel)) for rec in sample) / len(sample)
                for rel in relations}

    def link(self, q: Question) -> list[tuple[str, str]]:
        tokens = self.movie._normalize(q.text).split()
        if q.domain == "open":
            tables = [("open", self.open.key_map)]
        elif q.domain == "sports":
            tables = [("player", self.players)]
        elif q.domain == "music":
            tables = [("artist", self.artists), ("song", self.songs)]
        else:
            tables = [("movie", self.movies), ("person", self.persons)]
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

    def finance_facts(self, query: str) -> tuple[list[str], str]:
        if self.finance is None:
            return [], ""
        names = self.finance.get_company_name(query)
        if not names:
            return [], ""
        name = names[0]
        ticker = self.finance.get_ticker_by_name(name)
        if not ticker:
            return [], ""
        out = [f"{name} trades under the ticker symbol {ticker}."]
        for label, fn in (("market capitalisation",
                           self.finance.get_market_capitalization),
                          ("price to earnings ratio",
                           self.finance.get_pe_ratio),
                          ("earnings per share", self.finance.get_eps)):
            try:
                value = fn(ticker)
            except Exception:
                value = None
            if value is not None:
                shown = (spell_money(value) if label.startswith("market")
                         else f"{float(value):.2f}")
                out.append(f"The {label} of {name} ({ticker}) is {shown}.")
        try:
            info = self.finance.get_info(ticker) or {}
        except Exception:
            info = {}
        for key, label in (("sector", "sector"), ("industry", "industry"),
                           ("city", "city"), ("country", "country"),
                           ("fullTimeEmployees", "number of employees"),
                           ("website", "website")):
            if info.get(key):
                out.append(f"The {label} of {name} is {info[key]}.")
        for officer in (info.get("companyOfficers") or [])[:12]:
            if officer.get("name"):
                out.append(f"{officer.get('name')} is the "
                           f"{officer.get('title', 'an officer')} of {name}.")
        summary = str(info.get("longBusinessSummary") or "")
        for part in summary.split(". ")[:8]:
            if len(part) > 20:
                out.append(part.strip() + ".")
        try:
            divs = self.finance.get_dividends_history(ticker) or {}
        except Exception:
            divs = {}
        for day in sorted(divs)[-MAX_LIST:]:
            out.append(f"{name} ({ticker}) paid a dividend of "
                       f"{divs[day]} on {spell_date(str(day)[:10])}.")
        try:
            hist = self.finance.get_price_history(ticker) or {}
        except Exception:
            hist = {}
        for day in sorted(hist)[-MAX_LIST:]:
            row = hist[day] or {}
            close = row.get("close") if isinstance(row, dict) else None
            if close is not None:
                out.append(f"On {spell_date(str(day)[:10])} the closing "
                           f"share price of {name} ({ticker}) was "
                           f"{float(close):.2f} dollars.")
        return out, ticker

    def _charts(self, rank_dict: dict) -> dict[str, dict[int, set]]:
        out: dict[str, dict[int, set]] = {}
        for rank, rows in rank_dict.items():
            try:
                pos = int(rank)
            except (TypeError, ValueError):
                continue
            for row in rows:
                artist = self.movie._normalize(str(row.get("Artist", "")))
                if not artist:
                    continue
                out.setdefault(artist, {}).setdefault(pos, set()).add(
                    (str(row.get("Song", "")), str(row.get("Date", ""))))
        return out

    def chart_facts(self, name: str) -> list[str]:
        entry = self.charts.get(name)
        if not entry:
            return []
        out = []
        for pos in sorted(entry):
            songs = sorted(entry[pos])
            titles = sorted({s for s, _ in songs})
            if pos == 1:
                out.append(f"{name} has {len(titles)} number one hits on the "
                           f"Billboard Hot 100.")
                out.append(f"The number one hits by {name} are "
                           f"{', '.join(titles[:MAX_LIST])}.")
            for song, date in songs[:MAX_LIST]:
                out.append(f"{song} by {name} reached number {pos} on the "
                           f"Billboard Hot 100 on {spell_date(date)}.")
        return out

    def player_facts(self, name: str, rec: dict) -> list[str]:
        who = rec.get("display_first_last") or name
        out = []
        if rec.get("birthdate"):
            out.append(f"{who} was born on "
                       f"{spell_date(str(rec['birthdate'])[:10])}.")
        for key, phrase in (("school", "attended"), ("country", "is from"),
                            ("position", "plays the position of"),
                            ("team_name", "played for the")):
            if rec.get(key):
                out.append(f"{who} {phrase} {rec[key]}.")
        if rec.get("height"):
            out.append(f"{who} is {rec['height']} feet and inches tall.")
        if rec.get("weight"):
            out.append(f"{who} weighs {rec['weight']} pounds.")
        if rec.get("jersey"):
            out.append(f"{who} wore jersey number {rec['jersey']}.")
        if rec.get("draft_year"):
            out.append(f"{who} was drafted in {rec['draft_year']}, "
                       f"round {rec.get('draft_round')}, "
                       f"pick {rec.get('draft_number')}.")
        if rec.get("from_year") and rec.get("to_year"):
            start, end = str(rec["from_year"])[:4], str(rec["to_year"])[:4]
            out.append(f"{who} played in the NBA from {start} to {end}.")
        if str(rec.get("greatest_75_flag") or "").strip().lower() == "y":
            out.append(f"{who} is one of the NBA 75th anniversary team.")
        return out

    def artist_facts(self, name: str, rec: dict) -> list[str]:
        out = []
        if rec.get("birth_date"):
            out.append(f"{name} was born on {spell_date(rec['birth_date'])}.")
        if rec.get("country"):
            out.append(f"{name} is from {rec['country']}.")
        if rec.get("end_date"):
            out.append(f"{name} ended in {spell_date(rec['end_date'])}.")
        members = rec.get("members") or []
        if members:
            out.append(f"The members of {name} are "
                       f"{', '.join(members[:MAX_LIST])}.")
            for m in members[:MAX_LIST]:
                out.append(f"{m} is a member of {name}.")
        return out

    def song_facts(self, name: str, rec: dict) -> list[str]:
        out = []
        if rec.get("author"):
            out.append(f"The song {name} is by {rec['author']}.")
        if rec.get("date"):
            out.append(f"The song {name} was released in "
                       f"{spell_date(rec['date'])}.")
        if rec.get("country"):
            out.append(f"The song {name} was released in {rec['country']}.")
        return out

    def year_facts(self, year: str) -> list[str]:
        out = []
        for a in (self.years.get(year, {}).get("oscar_awards") or []):
            won = "won" if a.get("winner") else "was nominated for"
            out.append(f"In {year} {a.get('name')} {won} the Oscar for "
                       f"{a.get('category')} for the film {a.get('film')}.")
        return out


RELATION_TABLES = {"movie": MOVIE_RELATIONS, "person": PERSON_RELATIONS,
                   "artist": ARTIST_RELATIONS, "song": SONG_RELATIONS,
                   "player": PLAYER_RELATIONS}


def _relation(q: Question, kind: str) -> str | None:
    words = set(crag._tokens(q.text))
    for rel, cues in RELATION_TABLES.get(kind, {}).items():
        if words & set(cues):
            return rel
    return None


class KBSource:
    name = "K"

    def __init__(self, kb: KnowledgeBase | None = None) -> None:
        self.kb = kb or KnowledgeBase()

    def retrieve(self, q: Question) -> Evidence:
        kb = self.kb
        if q.domain == "finance":
            facts, ticker = kb.finance_facts(q.text)
            items = [{"entity": ticker, "text": f} for f in facts]
            return Evidence(source="K", items=items, meta={
                "entity_resolved": float(bool(ticker)),
                "relation_present": float(len(facts) > 1),
                "node_degree": float(len(facts)),
                "entity_type": "company",
                "type_coverage": 1.0 if ticker else 0.0,
                "n_entities": float(bool(ticker)),
                "link_tokens": float(len(ticker.split())) if ticker else 0.0})
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
            table = {"movie": kb.movies, "person": kb.persons,
                     "artist": kb.artists, "song": kb.songs,
                     "player": kb.players}[kind]
            rec = table[name]
            if kind == "movie":
                facts = kb.movie_facts(rec)
            elif kind == "person":
                facts = kb.person_facts(rec)
            elif kind == "player":
                facts = kb.player_facts(name, rec)
            elif kind == "artist":
                facts = kb.artist_facts(name, rec) + kb.chart_facts(name)
            else:
                facts = kb.song_facts(name, rec)
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
