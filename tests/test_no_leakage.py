"""Empirical proof that the stage-one probes cannot see the gold answer."""
from __future__ import annotations

import ast
import dataclasses
import inspect
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wk import classmodel, crag, probes, simulate
from wk.contract import Evidence, Question, Record

GOLD = "Ruth Caraway"
SENTINEL = "zqxwyv-sentinel-7731"
MUTANTS = (
    "Totally Unrelated Person",
    "",
    "Tomas Linde",
    "2019",
    SENTINEL,
    "yes",
    "N$12.3 million",
    GOLD.upper(),
)

FORBIDDEN_ATTRS = ("answer", "answers", "alt_ans")
FORBIDDEN_CALLS = ("run", "contains_answer", "class_of", "_gold_answer",
                   "_alt_answers", "evidence_text")
ANSWER_FIELDS = tuple(crag.ANSWER_KEYS) + tuple(crag.ALT_ANSWER_KEYS)

PROBE_MODULES = (probes, crag, simulate)


def question(answer: str = GOLD) -> Question:
    return Question(qid="x1", text="Who directed Silent Harbour?", answer=answer,
                    domain="movie", question_type="simple", dynamism="slow",
                    popularity="torso", n_hops=2)


def web_evidence() -> Evidence:
    return Evidence(
        source="W",
        items=[
            {"title": "Silent Harbour", "url": "http://example/1",
             "snippet": f"directed by {GOLD}", "score": 0.91,
             "text": f"Silent Harbour was directed by {GOLD} in 2019.",
             "date": "2019-05-01T10:00:00"},
            {"title": "Review", "url": "http://example/2",
             "snippet": "a film by Tomas Linde", "score": 0.44,
             "text": "A quiet film by Tomas Linde.",
             "date": "2021-01-01T10:00:00"},
            {"title": "Listing", "url": "http://example/3",
             "snippet": "", "score": 0.12, "text": "", "date": ""},
        ],
        meta={"backend": "test-web", "n_items": 3})


def kb_evidence() -> Evidence:
    return Evidence(
        source="K",
        items=[
            {"entity": "Silent Harbour", "entity_type": "movie",
             "relation": "director", "value": GOLD,
             "text": f"director: {GOLD}"},
            {"entity": "Silent Harbour", "entity_type": "movie",
             "relation": "year", "value": 2019, "text": "year: 2019"},
            {"entity": "Silent Harbour", "entity_type": "movie",
             "relation": "gross", "value": None, "text": "gross: None"},
        ],
        meta={"backend": "test-kb", "query_relation": "director", "n_nodes": 1,
              "node_degree": 3, "type_coverage": 0.67, "entity_type": "movie"})


def raw_item(answer: str = GOLD, alt: str = "R. Caraway") -> dict[str, Any]:
    return {
        "interaction_id": "x1",
        "query": "Who directed Silent Harbour?",
        "answer": answer,
        "alt_ans": [alt],
        "domain": "movie",
        "question_type": "simple",
        "static_or_dynamic": "slow",
        "popularity": "torso",
        "query_time": "05/01/2019, 10:00:00 PT",
        "search_results": [
            {"page_name": "Silent Harbour", "page_url": "http://example/1",
             "page_snippet": f"directed by {GOLD}",
             "page_result": f"<p>Silent Harbour, directed by {GOLD}.</p>",
             "page_last_modified": "2019-05-01 10:00:00"},
            {"page_name": "Review", "page_url": "http://example/2",
             "page_snippet": "a film by Tomas Linde",
             "page_result": "<p>A quiet film by Tomas Linde.</p>",
             "page_last_modified": "2021-01-01 10:00:00"},
        ],
        "kg_results": [
            {"name": "Silent Harbour", "type": "movie", "director": GOLD,
             "year": 2019, "gross": None},
        ],
    }


class AnswerTripwire:
    def __init__(self, q: Question) -> None:
        object.__setattr__(self, "_wrapped", q)

    def __getattr__(self, name: str) -> Any:
        if name in FORBIDDEN_ATTRS:
            raise AssertionError(f"a probe read Question.{name}")
        return getattr(object.__getattribute__(self, "_wrapped"), name)

    def __getitem__(self, name: str) -> Any:
        raise AssertionError(f"a probe subscripted the question with {name!r}")


class RunTripwireWeb(crag.CragWebSource):
    def run(self, q: Any, ev: Evidence, n: int = 10) -> Any:
        raise AssertionError("a probe called run()")


class RunTripwireKB(crag.CragKBSource):
    def run(self, q: Any, ev: Evidence, n: int = 10) -> Any:
        raise AssertionError("a probe called run()")


LEAKY_SOURCE = """
def helper(q, ev):
    return q.answer


def leaky_probe(q, ev):
    return {"cheat": float(helper(q, ev) in str(ev.items))}


def leaky_sampler(q, ev):
    return {"cheat": float(sampler(q, ev).majority_correct)}


def sampler(q, ev):
    return run(q, ev)
"""


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _definitions(trees: Iterable[ast.AST]) -> dict[str, list[ast.AST]]:
    table: dict[str, list[ast.AST]] = {}
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                table.setdefault(node.name, []).append(node)
    return table


def _module_trees(modules: Sequence[Any]) -> list[ast.AST]:
    return [ast.parse(inspect.getsource(module)) for module in modules]


def _closure(table: dict[str, list[ast.AST]],
             roots: Sequence[str]) -> dict[str, list[ast.AST]]:
    seen: dict[str, list[ast.AST]] = {}
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen or name not in table:
            continue
        seen[name] = table[name]
        for node in table[name]:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    nxt = _call_name(sub)
                    if nxt and nxt not in seen:
                        stack.append(nxt)
    return seen


def _violations(closure: dict[str, list[ast.AST]]) -> list[str]:
    found: list[str] = []
    for name, nodes in closure.items():
        for node in nodes:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and sub.attr in FORBIDDEN_ATTRS:
                    found.append(f"{name} reads .{sub.attr}")
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if sub.value.strip().lower() in ANSWER_FIELDS:
                        found.append(f"{name} keys on {sub.value!r}")
                if isinstance(sub, ast.Call) and _call_name(sub) in FORBIDDEN_CALLS:
                    found.append(f"{name} calls {_call_name(sub)}()")
    return sorted(set(found))


def probe_table() -> dict[str, list[ast.AST]]:
    return _definitions(_module_trees(PROBE_MODULES))


@pytest.fixture(autouse=True)
def isolated_raw_items(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    store: dict[str, Any] = {}
    monkeypatch.setattr(crag, "RAW_ITEMS", store)
    return store


@pytest.mark.parametrize("mutant", MUTANTS)
def test_probe_web_features_survive_answer_mutation(mutant: str) -> None:
    ev = web_evidence()
    before = probes.probe_web(question(), ev)
    after = probes.probe_web(question(mutant), ev)
    assert after == before, f"probe_web moved when the gold became {mutant!r}"


@pytest.mark.parametrize("mutant", MUTANTS)
def test_probe_kb_features_survive_answer_mutation(mutant: str) -> None:
    ev = kb_evidence()
    before = probes.probe_kb(question(), ev)
    after = probes.probe_kb(question(mutant), ev)
    assert after == before, f"probe_kb moved when the gold became {mutant!r}"


def test_probe_output_is_a_finite_number_per_declared_feature() -> None:
    web = probes.probe_web(question(), web_evidence())
    kb = probes.probe_kb(question(), kb_evidence())
    assert set(web) == set(probes.WEB_FEATURES)
    assert set(kb) == set(probes.KB_FEATURES)
    assert all(np.isfinite(v) for v in (*web.values(), *kb.values()))


def test_probes_do_respond_to_their_evidence() -> None:
    q = question()
    thin_web = Evidence(source="W", items=web_evidence().items[:1], meta={})
    thin_kb = Evidence(source="K", items=kb_evidence().items[1:], meta={})
    assert probes.probe_web(q, thin_web) != probes.probe_web(q, web_evidence())
    assert probes.probe_kb(q, thin_kb) != probes.probe_kb(q, kb_evidence())
    assert probes.probe_web(q, Evidence(source="W")) != probes.probe_web(
        q, web_evidence())


def test_probes_raise_nothing_when_the_answer_attribute_is_a_tripwire() -> None:
    tripped = AnswerTripwire(question())
    assert probes.probe_web(tripped, web_evidence()) == probes.probe_web(
        question(), web_evidence())
    assert probes.probe_kb(tripped, kb_evidence()) == probes.probe_kb(
        question(), kb_evidence())


def test_crag_probes_survive_mutation_of_the_stored_gold(
        isolated_raw_items: dict[str, Any]) -> None:
    isolated_raw_items["x1"] = raw_item()
    web, kb = crag.CragWebSource(), crag.CragKBSource()
    q = question()
    ev_w, ev_k = web.retrieve(q), kb.retrieve(q)
    before = (web.probe(q, ev_w), kb.probe(q, ev_k))
    assert web.contains_answer(q, ev_w) and kb.contains_answer(q, ev_k)

    isolated_raw_items["x1"] = raw_item(answer=SENTINEL, alt="nobody at all")
    q2 = question(SENTINEL)
    ev_w2, ev_k2 = web.retrieve(q2), kb.retrieve(q2)
    after = (web.probe(q2, ev_w2), kb.probe(q2, ev_k2))
    assert after == before, "a CRAG probe moved when only the gold changed"
    assert not web.contains_answer(q2, ev_w2)
    assert not kb.contains_answer(q2, ev_k2)


def test_crag_retrieval_is_invariant_to_the_stored_gold(
        isolated_raw_items: dict[str, Any]) -> None:
    for source in (crag.CragWebSource(), crag.CragKBSource()):
        isolated_raw_items["x1"] = raw_item()
        before = source.retrieve(question())
        isolated_raw_items["x1"] = raw_item(answer=SENTINEL, alt=SENTINEL)
        after = source.retrieve(question(SENTINEL))
        assert after.items == before.items
        assert after.meta == before.meta


def test_crag_evidence_keeps_no_trace_of_the_gold_answer(
        isolated_raw_items: dict[str, Any]) -> None:
    isolated_raw_items["x1"] = raw_item(answer=SENTINEL, alt=SENTINEL)
    q = question(SENTINEL)
    for source in (crag.CragWebSource(), crag.CragKBSource()):
        ev = source.retrieve(q)
        assert SENTINEL not in str(ev.meta)
        assert SENTINEL not in str(ev.items)
        assert not set(ev.meta) & set(ANSWER_FIELDS)


def test_crag_probes_do_not_call_run(isolated_raw_items: dict[str, Any]) -> None:
    isolated_raw_items["x1"] = raw_item()
    q = question()
    for source in (RunTripwireWeb(), RunTripwireKB()):
        ev = source.retrieve(q)
        assert set(source.probe(q, ev))
        assert isinstance(source.contains_answer(q, ev), bool)


def test_probe_closures_never_read_the_answer_or_sample() -> None:
    table = probe_table()
    for root in ("probe_web", "probe_kb"):
        closure = _closure(table, [root])
        assert len(closure) > 3, f"{root} closure looks too small to be real"
        assert _violations(closure) == []


def test_crag_source_closures_never_read_the_answer_or_sample() -> None:
    table = probe_table()
    closure = _closure(table, ["probe", "retrieve"])
    assert "probe_web" in closure and "probe_kb" in closure
    assert _violations(closure) == []


def test_simulator_probe_closures_never_read_the_answer() -> None:
    table = probe_table()
    closure = _closure(table, ["_probe_w", "_probe_k"])
    assert _violations(closure) == []


def test_probes_module_holds_no_handle_on_a_question_store() -> None:
    source = inspect.getsource(probes)
    assert "RAW_ITEMS" not in source
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not {"wk.crag", "crag", "wk.simulate", "simulate"} & imported


def test_the_leakage_checker_catches_a_planted_leak() -> None:
    table = _definitions([ast.parse(LEAKY_SOURCE)])
    assert any("reads .answer" in v for v in _violations(
        _closure(table, ["leaky_probe"])))
    assert any("calls run()" in v for v in _violations(
        _closure(table, ["leaky_sampler"])))


def test_the_leakage_checker_fires_on_contains_answer_itself() -> None:
    closure = _closure(probe_table(), ["contains_answer"])
    assert _violations(closure), "the checker is blind on a known reader of gold"


def test_contains_answer_tracks_the_gold_answer(
        isolated_raw_items: dict[str, Any]) -> None:
    isolated_raw_items["x1"] = raw_item()
    web, kb = crag.CragWebSource(), crag.CragKBSource()
    q = question()
    ev_w, ev_k = web.retrieve(q), kb.retrieve(q)
    assert web.contains_answer(q, ev_w) is True
    assert kb.contains_answer(q, ev_k) is True
    for mutant in ("Totally Unrelated Person", SENTINEL, "Priya Nandakumar"):
        assert web.contains_answer(question(mutant), ev_w) is False
        assert kb.contains_answer(question(mutant), ev_k) is False


def test_contains_answer_accepts_the_published_alternatives(
        isolated_raw_items: dict[str, Any]) -> None:
    isolated_raw_items["x1"] = raw_item(answer=SENTINEL, alt=GOLD)
    web = crag.CragWebSource()
    q = question(SENTINEL)
    assert web.contains_answer(q, web.retrieve(q)) is True


def test_feature_matrix_reads_rho_and_nothing_else() -> None:
    records = simulate.make_synthetic(40, seed=5)
    for source in simulate.SOURCES:
        X, names = probes.feature_matrix(records, source)
        assert names == sorted(set(names))
        wrecked = [
            Record(question=dataclasses.replace(rec.question, answer=SENTINEL),
                   rho=rec.rho,
                   membership={k: not v for k, v in rec.membership.items()},
                   runs={},
                   truth={"class_W": "ghost", "class_K": "ghost"})
            for rec in records]
        Y, other = probes.feature_matrix(wrecked, source)
        assert other == names
        assert np.array_equal(X, Y, equal_nan=True)


def test_simulated_rho_carries_only_the_declared_probe_features() -> None:
    for rec in simulate.make_synthetic(60, seed=6):
        assert set(rec.rho["W"]) == set(probes.WEB_FEATURES)
        assert set(rec.rho["K"]) == set(probes.KB_FEATURES)
        assert not set(rec.rho) & {"truth", "membership", "runs"}
        for block in rec.rho.values():
            assert all(np.isfinite(v) for v in block.values())


@pytest.mark.parametrize("source", ("W", "K"))
def test_no_simulated_feature_separates_the_classes_perfectly(
        source: str) -> None:
    records = simulate.make_synthetic(600, seed=7)
    X, names = probes.feature_matrix(records, source)
    y = classmodel.labels(records, source)
    for j, name in enumerate(names):
        for label in np.unique(y):
            auc = roc_auc_score((y == label).astype(int), X[:, j])
            assert 0.005 < auc < 0.995, f"{source}.{name} pins {label}"
    macro = classmodel.cross_val_auroc(X, y)["macro"]
    assert 0.5 < macro < 0.995, f"{source} macro AUROC of {macro} is not learning"
