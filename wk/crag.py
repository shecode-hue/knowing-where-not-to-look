"""Adapter from the CRAG benchmark release onto the W and K source contract."""
from __future__ import annotations

import bz2
import gzip
import json
import re
import unicodedata
from dataclasses import replace
from datetime import datetime
from html import unescape
from itertools import chain
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

try:
    from wk.contract import (DYNAMISM, POPULARITY, Evidence, Question, Record,
                             SourceRun)
except ImportError:
    from contract import (DYNAMISM, POPULARITY, Evidence, Question, Record,
                          SourceRun)

CRAG_URL = "https://github.com/facebookresearch/CRAG"
CRAG_PAPER_URL = "https://arxiv.org/abs/2406.04744"
CRAG_LICENCE = "CC BY-NC 4.0, non-commercial research use"
CRAG_FILES = (
    "data/crag_task_1_and_2_dev_v4.jsonl.bz2",
    "data/crag_task_3_dev_v4.tar.bz2",
)

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "crag"

DOWNLOAD_HINT = f"""CRAG is not bundled with this repository and is not on this box.

To obtain it:
  1. install git-lfs once:            git lfs install
  2. clone the release repository:    git clone {CRAG_URL}
  3. pull the large files:            cd CRAG && git lfs pull
  4. the question files are the jsonl releases under data/, expected names
     being {CRAG_FILES[0]} for tasks 1 and 2 (mock web search plus mock
     knowledge-graph records behind the same questions) and {CRAG_FILES[1]}
     for task 3 (the wider web page set per question)
  5. copy or symlink the jsonl into {DEFAULT_PATH} and pass that directory,
     or any single file, to load_crag(); .jsonl, .jsonl.bz2 and .jsonl.gz are
     read directly, so there is no need to decompress first
  6. task 3 ships as a tar archive, so untar it and point load_crag() at the
     extracted jsonl rather than at the tarball

If the KDD Cup 2024 CRAG mirror is easier to reach than git-lfs, the same
jsonl files are published on the AIcrowd challenge data pages; field names
differ slightly between tasks, which this adapter tolerates by reading every
field with .get() and recording anything it cannot map in UNMAPPED_FIELDS.

The paper describes 4409 question and answer pairs over 5 domains, 8 question
categories, head, torso and tail entity popularity and dynamism from years to
seconds. A public release may carry only part of that, so treat the loaded
count as whatever the file holds rather than as the full benchmark.

Licence: {CRAG_LICENCE}. Check available() before loading and fall back to
wk.simulate when it returns False."""

NORMALISER_DOC = """contains_answer() normaliser, applied to both the gold answer
and the concatenated evidence text: Unicode NFKD decomposition with combining
marks dropped, lowercasing, every character outside [0-9a-z] replaced by a
space, then whitespace collapsed. Matching is on token sequences rather than
raw substrings, so the answer "no" cannot match inside "nobody" and "2 1" cannot
match inside "2 10". The CRAG alternative answers, where the release ships them,
count as gold as well, since membership asks whether the corpus expresses the
answer at all. The no-answer sentinels in NO_ANSWER are never treated as
present. Boolean answers such as yes and no still match almost any page, so
exclude those question types upstream rather than trusting membership on them."""

EVIDENCE_DOC = """Evidence shapes, chosen to match what wk.probes reads.

W items are one dict per mock search result: title, url, snippet, text,
last_modified and date. text is the page HTML with script, style and tags
stripped and whitespace collapsed, falling back to the snippet when the
release carries no page body. snippet is kept separate because it is the
short span probe_web compares across pages, and date is last_modified
rewritten to ISO 8601 so the recency probe can read it.

K items are one dict per knowledge-graph fact, not one per node: entity,
entity_type, relation, value and text, where relation is the dotted path
through the mock knowledge-graph record. That is the granularity probe_kb
needs for relation_present. Evidence meta carries n_nodes, node_degree as
the fact count of the largest returned node, entity_type, and type_coverage
read as the schema fill rate, meaning the share of returned relations that
hold a non-empty value. CRAG publishes no per-type relation coverage table,
so the fill rate stands in for it rather than a fabricated figure.

An entity falls back to a synthetic crag-kg-node-N label when the record
carries no name field, since the mock knowledge graph returns records only
for an entity it resolved; an empty item list is the unresolved case."""

RUN_STUB_MESSAGE = (
    "{name}.run() is a stage-3 entry point and is deliberately not implemented "
    "in the CRAG adapter. Drawing n answers needs a live per-source agent for "
    "{name} together with an LLM API key, which this offline adapter does not "
    "carry; it only replays the retrieval the benchmark ships. Stage 1 needs "
    "retrieve(), probe() and contains_answer() alone. Wire the agent in stage 3, "
    "or use wk.simulate for synthetic runs."
)

UNMAPPED_FIELDS: set[str] = set()
RAW_ITEMS: dict[str, dict[str, Any]] = {}

QUERY_KEYS = ("query", "question", "question_text")
ANSWER_KEYS = ("answer", "ground_truth", "gold_answer")
ALT_ANSWER_KEYS = ("alt_ans", "alt_answers", "answers", "acceptable_answers")
WEB_KEYS = ("search_results", "web_search_results", "page_results", "pages")
KB_KEYS = ("kg_results", "kg_records", "knowledge_graph", "mock_kg", "kg",
           "api_results", "mock_api_results", "structured_results")

DYNAMISM_MAP = {
    "static": "static",
    "slow": "slow", "slow-changing": "slow", "slowly-changing": "slow",
    "fast": "fast", "fast-changing": "fast", "rapidly-changing": "fast",
    "realtime": "realtime", "real-time": "realtime", "live": "realtime",
}
POPULARITY_KEYS = ("popularity", "entity_popularity", "popularity_bucket",
                   "head_torso_tail", "entity_pop")
POPULARITY_MAP = {
    "head": "head", "popular": "head", "high": "head",
    "torso": "torso", "medium": "torso", "mid": "torso",
    "tail": "tail", "rare": "tail", "low": "tail", "long-tail": "tail",
}
HOPS_BY_TYPE = {"multi-hop": 2, "multihop": 2, "comparison": 2}
HOPS_KEYS = ("n_hops", "num_hops", "hops")

ENTITY_KEYS = ("name", "entity", "entity_name", "title", "symbol", "ticker")
ENTITY_TYPE_KEYS = ("type", "entity_type", "category", "kind")
EMPTY_VALUES = (None, "", [], {}, ())
DATE_FORMATS = (
    "%m/%d/%Y, %H:%M:%S PT",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d",
    "%d %B %Y",
    "%B %d, %Y",
)

NO_ANSWER = frozenset({
    "", "invalid question", "i dont know", "i do not know", "unknown",
    "no answer", "none",
})

STOPWORDS = frozenset("""
a an the of in on at to for from by with and or but is are was were be been
being has have had do does did it its this that these those as than then
which who whom whose what when where why how there their they them he she
his her him we our you your i me my not no so if into over under about
also all any each other more most some such only own same just can will
would should could may might total number
""".split())

ANSWER_RECALL = 0.8

KNOWN_FIELDS = frozenset(
    QUERY_KEYS + ANSWER_KEYS + ALT_ANSWER_KEYS + WEB_KEYS + KB_KEYS
    + POPULARITY_KEYS + HOPS_KEYS
    + ("interaction_id", "id", "qid", "domain", "question_type",
       "static_or_dynamic", "dynamism", "query_time", "split", "task",
       "source", "answer_type")
)

_NON_WORD = re.compile(r"[^0-9a-z]+")
_SCRIPTISH = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def _probes():
    try:
        from wk import probes
    except ImportError:
        import probes
    return probes


def normalise(text: Any) -> str:
    folded = unicodedata.normalize("NFKD", str(text)).lower()
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(_NON_WORD.sub(" ", folded).split())


def strip_html(raw: Any) -> str:
    text = str(raw or "")
    if not text:
        return ""
    if "<" in text:
        text = _TAG.sub(" ", _SCRIPTISH.sub(" ", text))
    return " ".join(unescape(text).split())


def iso_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).isoformat()
        except ValueError:
            continue
    UNMAPPED_FIELDS.add(f"unparsed_date_format={text[:24]!r}")
    return ""


def kg_facts(node: Any, prefix: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            out.extend(kg_facts(value, f"{prefix} {key}".strip()))
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            out.extend(kg_facts(value, prefix))
    else:
        out.append((prefix, node))
    return out


def flatten_kg(node: Any, prefix: str = "") -> list[str]:
    return [f"{relation}: {value}".lstrip(": ").strip()
            for relation, value in kg_facts(node, prefix)
            if value not in EMPTY_VALUES]


def evidence_text(ev: Evidence) -> str:
    parts: list[str] = []
    for item in ev.items:
        if isinstance(item, dict):
            parts.extend(str(value) for value in item.values())
        elif isinstance(item, (list, tuple)):
            parts.extend(str(value) for value in item)
        else:
            parts.append(str(item))
    return " ".join(parts)


def _tokens(text: Any) -> list[str]:
    return normalise(text).split()


def _contains_tokens(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    span = len(needle)
    if span == 0 or span > len(haystack):
        return False
    lead = needle[0]
    for i, token in enumerate(haystack):
        if token == lead and list(haystack[i:i + span]) == list(needle):
            return True
    return False


def answer_tokens(gold: Any, question: Any) -> set[str]:
    asked = set(_tokens(question))
    return {t for t in _tokens(gold) if t not in STOPWORDS and t not in asked}


def answer_present(gold: Any, question: Any, haystack: Sequence[str]) -> bool:
    needle = normalise(gold)
    if needle in NO_ANSWER:
        return False
    if _contains_tokens(haystack, needle.split()):
        return True
    wanted = answer_tokens(gold, question)
    if not wanted:
        return False
    seen = set(haystack)
    return sum(t in seen for t in wanted) / len(wanted) >= ANSWER_RECALL


def _first_present(item: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value:
            return value
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _is_data_file(path: Path) -> bool:
    name = path.name.lower()
    if name.startswith("."):
        return False
    return name.endswith((".jsonl", ".json", ".jsonl.bz2", ".jsonl.gz",
                          ".json.bz2", ".json.gz"))


def _candidate_files(path: str | Path | None) -> list[Path]:
    target = Path(path if path is not None else DEFAULT_PATH).expanduser()
    if target.is_file():
        return [target] if _is_data_file(target) else []
    if target.is_dir():
        return [f for f in sorted(target.rglob("*"))
                if f.is_file() and _is_data_file(f)]
    return []


def _open_text(path: Path):
    name = path.name.lower()
    if name.endswith(".bz2"):
        return bz2.open(path, "rt", encoding="utf-8", errors="replace")
    if name.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("rt", encoding="utf-8", errors="replace")


def _iter_items(path: Path) -> Iterator[dict[str, Any]]:
    with _open_text(path) as handle:
        first = handle.readline()
        if first.lstrip().startswith("["):
            for item in json.loads(first + handle.read()):
                if isinstance(item, dict):
                    yield item
            return
        for line in chain([first], handle):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                UNMAPPED_FIELDS.add(f"unparsable_line:{path.name}")
                continue
            if isinstance(item, dict):
                yield item


def _record_unmapped(item: dict[str, Any]) -> None:
    for key in item:
        if key not in KNOWN_FIELDS:
            UNMAPPED_FIELDS.add(key)


def _gold_answer(item: dict[str, Any]) -> str:
    value = _first_present(item, ANSWER_KEYS)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def _alt_answers(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ALT_ANSWER_KEYS:
        for value in _as_list(item.get(key)):
            if isinstance(value, (str, int, float)):
                out.append(str(value).strip())
    return [a for a in out if a]


def _map_dynamism(item: dict[str, Any]) -> str:
    raw = _first_present(item, ("static_or_dynamic", "dynamism")) or "static"
    key = str(raw).strip().lower().replace("_", "-").replace(" ", "-")
    value = DYNAMISM_MAP.get(key)
    if value is None or value not in DYNAMISM:
        UNMAPPED_FIELDS.add(f"static_or_dynamic={key}")
        return DYNAMISM[0]
    return value


def _map_popularity(item: dict[str, Any]) -> str:
    raw = _first_present(item, POPULARITY_KEYS)
    if raw is None:
        return "head"
    key = str(raw).strip().lower().replace("_", "-").replace(" ", "-")
    value = POPULARITY_MAP.get(key)
    if value is None or value not in POPULARITY:
        UNMAPPED_FIELDS.add(f"popularity={key}")
        return "head"
    return value


def _map_hops(item: dict[str, Any], question_type: str) -> int:
    for key in HOPS_KEYS:
        raw = item.get(key)
        if raw is None:
            continue
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            UNMAPPED_FIELDS.add(f"{key}={raw!r}")
    return HOPS_BY_TYPE.get(question_type.replace("_", "-"), 1)


def _to_question(item: dict[str, Any], fallback_qid: str) -> Question:
    _record_unmapped(item)
    qid = str(_first_present(item, ("interaction_id", "id", "qid"))
              or fallback_qid)
    question_type = str(item.get("question_type") or "simple").strip().lower()
    return Question(
        qid=qid,
        text=str(_first_present(item, QUERY_KEYS) or "").strip(),
        answer=_gold_answer(item),
        domain=str(item.get("domain") or "unknown").strip().lower() or "unknown",
        question_type=question_type or "simple",
        dynamism=_map_dynamism(item),
        popularity=_map_popularity(item),
        n_hops=_map_hops(item, question_type),
    )


def load_crag(path: str | Path | None = None,
              limit: int | None = None) -> list[Question]:
    files = _candidate_files(path)
    if not files:
        where = path if path is not None else DEFAULT_PATH
        raise FileNotFoundError(f"No CRAG jsonl found at {where}."
                                f"\n\n{DOWNLOAD_HINT}")
    questions: list[Question] = []
    for file in files:
        for index, item in enumerate(_iter_items(file)):
            if limit is not None and len(questions) >= limit:
                return questions
            question = _to_question(item, f"{file.name}-{index:05d}")
            RAW_ITEMS[question.qid] = item
            questions.append(question)
    return questions


class _CragSource:
    name = "crag"
    payload_keys: tuple[str, ...] = ()
    backend = "crag"

    def __init__(self, raw: dict[str, dict[str, Any]] | None = None,
                 max_chars: int | None = None) -> None:
        self.raw = RAW_ITEMS if raw is None else raw
        self.max_chars = max_chars

    def item(self, q: Question) -> dict[str, Any]:
        return self.raw.get(q.qid, {})

    def _clip(self, text: str) -> str:
        if self.max_chars is None or self.max_chars <= 0:
            return text
        return text[:self.max_chars]

    def _payload(self, q: Question) -> list[Any]:
        return _as_list(_first_present(self.item(q), self.payload_keys))

    def _evidence(self, q: Question, items: list[Any]) -> Evidence:
        item = self.item(q)
        return Evidence(
            source=self.name,
            items=items,
            meta={"backend": self.backend,
                  "n_items": len(items),
                  "query_time": str(item.get("query_time") or ""),
                  "attached": bool(item),
                  "max_chars": self.max_chars})

    def contains_answer(self, q: Question, ev: Evidence) -> bool:
        haystack = _tokens(evidence_text(ev))
        if not haystack:
            return False
        golds = [q.answer, *_alt_answers(self.item(q))]
        return any(answer_present(g, q.text, haystack) for g in golds)

    def run(self, q: Question, ev: Evidence, n: int = 10) -> SourceRun:
        from wk.baseline_agent import run_extractive
        return replace(run_extractive(q, ev, n=n), source=self.name)


class CragWebSource(_CragSource):
    name = "W"
    payload_keys = WEB_KEYS
    backend = "crag-mock-web-search"

    def retrieve(self, q: Question) -> Evidence:
        return self._evidence(q, [self._page(p) for p in self._payload(q)])

    def probe(self, q: Question, ev: Evidence) -> dict[str, float]:
        return _probes().probe_web(q, ev)

    def _page(self, page: Any) -> dict[str, Any]:
        if not isinstance(page, dict):
            return {"title": "", "url": "", "snippet": "", "date": "",
                    "text": self._clip(strip_html(page)), "last_modified": ""}
        snippet = strip_html(page.get("page_snippet"))
        body = strip_html(page.get("page_result") or page.get("page_content"))
        stamp = str(page.get("page_last_modified") or "")
        return {"title": str(page.get("page_name") or ""),
                "url": str(page.get("page_url") or ""),
                "snippet": snippet,
                "text": self._clip(body or snippet),
                "last_modified": stamp,
                "date": iso_date(stamp)}


class CragKBSource(_CragSource):
    name = "K"
    payload_keys = KB_KEYS
    backend = "crag-mock-knowledge-graph"

    def retrieve(self, q: Question) -> Evidence:
        nodes = self._payload(q)
        items: list[dict[str, Any]] = []
        filled = 0
        degrees: list[int] = []
        for index, node in enumerate(nodes):
            entity = self._entity(node, index)
            entity_type = self._entity_type(node)
            facts = kg_facts(node)
            degrees.append(sum(1 for _, v in facts if v not in EMPTY_VALUES))
            filled += degrees[-1]
            for relation, value in facts:
                items.append({"entity": entity,
                              "entity_type": entity_type,
                              "relation": relation,
                              "value": value,
                              "text": self._clip(f"{relation}: {value}")})
        ev = self._evidence(q, items)
        ev.meta["n_nodes"] = len(nodes)
        ev.meta["node_degree"] = max(degrees) if degrees else 0
        ev.meta["type_coverage"] = filled / len(items) if items else 0.0
        ev.meta["entity_type"] = items[0]["entity_type"] if items else ""
        return ev

    def probe(self, q: Question, ev: Evidence) -> dict[str, float]:
        return _probes().probe_kb(q, ev)

    def _entity(self, node: Any, index: int) -> str:
        if isinstance(node, dict):
            name = _first_present(node, ENTITY_KEYS)
            if isinstance(name, (str, int, float)) and str(name).strip():
                return str(name).strip()
        return f"crag-kg-node-{index}"

    def _entity_type(self, node: Any) -> str:
        if isinstance(node, dict):
            value = _first_present(node, ENTITY_TYPE_KEYS)
            if isinstance(value, (str, int, float)):
                return str(value).strip()
        return ""


def build_records(questions: Iterable[Question],
                  sources: Sequence[Any]) -> list[Record]:
    records: list[Record] = []
    for q in questions:
        rec = Record(question=q, truth={"dataset": "crag", "n_evidence": {}})
        for source in sources:
            ev = source.retrieve(q)
            rec.rho[source.name] = source.probe(q, ev)
            rec.membership[source.name] = source.contains_answer(q, ev)
            rec.truth["n_evidence"][source.name] = len(ev.items)
        records.append(rec)
    return records


def available(path: str | Path | None = None) -> bool:
    return bool(_candidate_files(path))


def describe() -> str:
    files = _candidate_files(None)
    lines = [
        "CRAG adapter for the W (open web) and K (curated knowledge base) arms.",
        f"Benchmark: Comprehensive RAG Benchmark, {CRAG_PAPER_URL}",
        f"Release:   {CRAG_URL} ({CRAG_LICENCE})",
        "Design:    one question, two corpora. W replays the mock web search "
        "pages and K replays the mock knowledge-graph records, so ghost mass "
        "and rare passage are measured against the same wording.",
        f"Expected:  {DEFAULT_PATH}",
        f"Status:    {'data found' if files else 'data missing'}",
    ]
    if files:
        lines.append("Files:     " + ", ".join(f.name for f in files[:8]))
    else:
        lines.append("Fallback:  use wk.simulate instead; see DOWNLOAD_HINT "
                     "for how to obtain the real release.")
    lines.append(f"Loaded:    {len(RAW_ITEMS)} CRAG items held in RAW_ITEMS")
    if UNMAPPED_FIELDS:
        lines.append("Unmapped:  " + ", ".join(sorted(UNMAPPED_FIELDS)))
    lines.append("run() is a stage-3 stub; stage 1 uses retrieve, probe and "
                 "contains_answer only.")
    return "\n".join(lines)
