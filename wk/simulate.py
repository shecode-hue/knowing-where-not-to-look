"""Synthetic W/K benchmark with known ground truth, used to validate the estimators."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable, Sequence, TypeVar

import numpy as np

from wk.contract import DYNAMISM, POPULARITY, Question, Record, SourceRun, class_of

__all__ = ["STALENESS", "SOURCES", "make_synthetic", "write_jsonl", "read_jsonl"]

SOURCES: tuple[str, str] = ("W", "K")

STALENESS: dict[str, float] = {
    "static": 0.4,
    "slow": 0.8,
    "fast": 1.2,
    "realtime": 1.6,
}

DOMAINS: tuple[str, ...] = ("finance", "sports", "music", "movie", "open")

QUESTION_TYPES: tuple[str, ...] = (
    "simple",
    "simple_w_condition",
    "set",
    "comparison",
    "aggregation",
    "multi_hop",
    "post_processing",
    "false_premise",
)

HOPS: dict[str, tuple[int, int]] = {
    "simple": (1, 1),
    "simple_w_condition": (1, 2),
    "set": (1, 2),
    "comparison": (2, 3),
    "aggregation": (2, 3),
    "multi_hop": (2, 4),
    "post_processing": (1, 3),
    "false_premise": (1, 2),
}

ENTITIES: dict[str, tuple[str, ...]] = {
    "finance": ("Calder Pacific", "Northwind Energy", "Veltrix Holdings",
                "Marabou Capital", "Orinoco Freight"),
    "sports": ("Harbour City FC", "the Kalahari Lions", "Westfold United",
               "the Granite Bay Rowers", "the Cape Comets"),
    "music": ("Lila Osei", "the Dust Harbour Quartet", "Nomad Avenue",
              "Jun Takeda", "Saria Belkacem"),
    "movie": ("Silent Harbour", "The Ninth Monsoon", "Hollow Tide",
              "Carriage of Bells", "Last Light at Dawn"),
    "open": ("the Vela Transit Array", "the Okavango Flood Index",
             "the Lindgren Prize", "the Tasman Ferry Line",
             "the Arclight Observatory"),
}

STEMS: dict[str, tuple[tuple[str, str], ...]] = {
    "finance": (("What was the closing share price of {e} {t}", "price"),
                ("How much turnover did {e} report {t}", "sum"),
                ("How many {e} shares changed hands {t}", "volume")),
    "sports": (("Who did {e} play {t}", "team"),
               ("What was the final score for {e} {t}", "score"),
               ("How many points did {e} concede {t}", "points")),
    "music": (("Which album did {e} release {t}", "title"),
              ("Where did {e} perform {t}", "venue"),
              ("Who produced the latest single by {e}", "person")),
    "movie": (("Who directed {e}", "person"),
              ("What did {e} take at the box office {t}", "sum"),
              ("Which award did {e} win {t}", "award")),
    "open": (("Who has led {e} {t}", "person"),
             ("What is the reported size of {e} {t}", "length"),
             ("Which organisation funds {e} {t}", "org")),
}

TIMES: dict[str, tuple[str, ...]] = {
    "static": ("in 1998", "in 2004", "historically"),
    "slow": ("last year", "in the 2023 season", "over the past decade"),
    "fast": ("this week", "in the last few days", "since Monday"),
    "realtime": ("right now", "as of this minute", "at the time of asking"),
}

QUALIFIERS: dict[str, tuple[str, ...]] = {
    "simple": ("",),
    "simple_w_condition": (", under the published terms", ", on the main listing"),
    "set": (" (list every one)", " (all of them)"),
    "comparison": (", compared with the period before",
                   ", relative to the previous entry"),
    "aggregation": (", in total", ", across the whole period"),
    "multi_hop": (", and who signed that off", ", and where was that recorded"),
    "post_processing": (", according to the official record",
                        ", as given in the final listing"),
    "false_premise": (", after the cancellation", ", following the withdrawal"),
}

TITLES: tuple[str, ...] = (
    "Glasshouse", "Mirrorwork", "Salt and Signal", "The Long Veranda",
    "Pale Orbit", "Kalahari Blue", "Nine Rivers", "Tinwork",
    "The Quiet Exchange", "Harbour Lights", "Second Monsoon", "Dust Atlas",
)

PEOPLE: tuple[str, ...] = (
    "Ayanda Mokoena", "Ruth Caraway", "Tomas Linde", "Priya Nandakumar",
    "Felix Osterhagen", "Neo Sibanda", "Hester Veldman",
)

ORGS: tuple[str, ...] = (
    "the Hallward Trust", "the Southern Science Fund", "Meridian Foundation",
    "the Kalahari Research Council", "the Linde Institute",
    "Blue Harbour Capital", "the Tasman Endowment",
)

VENUES: tuple[str, ...] = (
    "the Atlas Theatre", "Harbour Park", "the Dome at Sandfontein",
    "Riverside Hall", "the Old Brewery Yard", "Vineyard Amphitheatre",
    "the Granite Bay Arena",
)

AWARDS: tuple[str, ...] = (
    "the Golden Kestrel", "Best Original Score", "the Critics' Circle Award",
    "Best Cinematography", "the Silver Arc", "Best Supporting Actress",
    "the Harbour Jury Prize",
)

TEAMS: tuple[str, ...] = (
    "Harbour City FC", "the Kalahari Lions", "Westfold United",
    "the Granite Bay Rowers", "the Cape Comets", "Ironvale Athletic",
    "Port Ridge Rovers",
)

BANKS: dict[str, tuple[str, ...]] = {
    "title": TITLES,
    "person": PEOPLE,
    "org": ORGS,
    "venue": VENUES,
    "award": AWARDS,
    "team": TEAMS,
}

POP_WEIGHT: dict[str, float] = {"head": 1.0, "torso": 0.55, "tail": 0.22}

SPREAD: dict[str, float] = {
    "static": 2200.0,
    "slow": 820.0,
    "fast": 160.0,
    "realtime": 35.0,
}

FRESHNESS: dict[str, float] = {
    "static": 0.0,
    "slow": 0.04,
    "fast": 0.10,
    "realtime": 0.14,
}

SD_LATENT = 0.78
SD_FEATURE = 0.07


T = TypeVar("T")


def _pick(rng: np.random.Generator, options: Sequence[T]) -> T:
    return options[int(rng.integers(len(options)))]


def _unit(x: float) -> float:
    return round(float(np.clip(x, 0.0, 1.0)), 6)


def _answers(rng: np.random.Generator, kind: str, k: int,
             avoid: str | None = None) -> list[str]:
    if kind == "price":
        vals = rng.choice(np.arange(250, 30000), size=k, replace=False)
        return [f"N${int(v) / 100:.2f}" for v in vals]
    if kind == "sum":
        vals = rng.choice(np.arange(12, 4000), size=k, replace=False)
        return [f"N${int(v) / 10:.1f} million" for v in vals]
    if kind == "volume":
        vals = rng.choice(np.arange(5, 9000), size=k, replace=False)
        return [f"{int(v) * 1000:,} shares" for v in vals]
    if kind == "score":
        vals = rng.choice(np.arange(0, 100), size=k, replace=False)
        return [f"{int(v) // 10}-{int(v) % 10}" for v in vals]
    if kind == "points":
        vals = rng.choice(np.arange(0, 130), size=k, replace=False)
        return [f"{int(v)} points" for v in vals]
    if kind == "length":
        vals = rng.choice(np.arange(5, 900), size=k, replace=False)
        return [f"{int(v)} km" for v in vals]
    pool = [x for x in BANKS[kind] if x != avoid]
    idx = rng.choice(len(pool), size=k, replace=False)
    return [pool[int(i)] for i in idx]


def _question(rng: np.random.Generator, i: int) -> tuple[Question, list[str]]:
    domain = _pick(rng, DOMAINS)
    question_type = _pick(rng, QUESTION_TYPES)
    dynamism = _pick(rng, DYNAMISM)
    popularity = _pick(rng, POPULARITY)
    lo, hi = HOPS[question_type]
    n_hops = int(rng.integers(lo, hi + 1))
    entity = _pick(rng, ENTITIES[domain])
    stem, kind = _pick(rng, STEMS[domain])
    when = _pick(rng, TIMES[dynamism])
    tail = _pick(rng, QUALIFIERS[question_type])
    text = " ".join(stem.format(e=entity, t=when).split()) + tail + "?"
    gold, *distractors = _answers(rng, kind, 5, avoid=entity)
    q = Question(qid=f"q{i:04d}", text=text, answer=gold, domain=domain,
                 question_type=question_type, dynamism=dynamism,
                 popularity=popularity, n_hops=n_hops)
    return q, list(distractors)


def _scatter(rng: np.random.Generator, m: int, distractors: Sequence[str],
             p_none: float) -> list[str | None]:
    out: list[str | None] = []
    for _ in range(m):
        if rng.random() < p_none:
            out.append(None)
        else:
            out.append(distractors[int(rng.integers(len(distractors)))])
    return out


def _shuffled(rng: np.random.Generator, qid: str, source: str,
              answers: Sequence[str | None],
              correct: Sequence[bool]) -> SourceRun:
    order = rng.permutation(len(answers))
    return SourceRun(qid=qid, source=source,
                     answers=[answers[int(i)] for i in order],
                     correct=[bool(correct[int(i)]) for i in order])


def _run(rng: np.random.Generator, qid: str, source: str, gold: str,
         distractors: Sequence[str], member: bool, agent_correct: bool,
         n_traces: int, ghost_confident: float) -> tuple[SourceRun, bool]:
    if n_traces < 1:
        raise ValueError("n_traces must be at least 1")
    if not member:
        confident = bool(rng.random() < ghost_confident)
        if confident:
            wrong = distractors[int(rng.integers(len(distractors)))]
            stragglers = int(rng.integers(0, n_traces // 4 + 1))
            k = n_traces - stragglers
            answers = [wrong] * k + _scatter(rng, stragglers, distractors, 0.5)
        else:
            answers = [None] * n_traces
        return _shuffled(rng, qid, source, answers, [False] * n_traces), confident
    if agent_correct:
        p_agree = float(rng.uniform(0.70, 0.97))
        k = int(rng.binomial(n_traces, p_agree))
        k = min(max(k, n_traces // 2 + 1), n_traces)
        answers = [gold] * k + _scatter(rng, n_traces - k, distractors, 0.25)
    else:
        answers = _scatter(rng, n_traces, distractors, 0.18)
    correct = [a == gold for a in answers]
    return _shuffled(rng, qid, source, answers, correct), False


def _probe_w(rng: np.random.Generator, q: Question, member: bool,
             agent_correct: bool) -> dict[str, float]:
    cov = 1.0 if member else 0.0
    ret = 1.0 if (member and agent_correct) else 0.0
    sc = cov + rng.normal(0.0, SD_LATENT)
    su = ret + rng.normal(0.0, SD_LATENT)
    weight = POP_WEIGHT[q.popularity]
    reach = float(np.clip(0.30 + 0.45 * sc + 0.20 * su, 0.0, 1.4))
    hits = float(int(np.clip(2.0 + 30.0 * weight * reach + rng.normal(0.0, 1.5),
                             0.0, 200.0)))
    agree = 0.20 + 0.30 * sc + 0.34 * su + rng.normal(0.0, SD_FEATURE)
    contra = 0.58 - 0.26 * sc - 0.24 * su + rng.normal(0.0, SD_FEATURE)
    spread = SPREAD[q.dynamism] * float(np.exp(rng.normal(0.0, 0.45)))
    spread += 240.0 * (1.0 - cov)
    if hits < 2.0:
        agree, contra, spread = 0.0, 0.0, 0.0
    return {
        "n_hits": hits,
        "agreement_at_10": _unit(agree),
        "contradiction_rate": _unit(contra),
        "recency_spread_days": round(float(spread), 3),
    }


def _probe_k(rng: np.random.Generator, q: Question, member: bool,
             agent_correct: bool) -> dict[str, float]:
    cov = 1.0 if member else 0.0
    ret = 1.0 if (member and agent_correct) else 0.0
    sc = cov + rng.normal(0.0, SD_LATENT)
    su = ret + rng.normal(0.0, SD_LATENT)
    weight = POP_WEIGHT[q.popularity]
    stale = FRESHNESS[q.dynamism]
    hop_cost = 0.05 * (q.n_hops - 1)
    p_resolved = _unit(0.34 + 0.46 * sc + 0.16 * su - 0.5 * stale)
    p_relation = _unit(0.20 + 0.54 * sc + 0.24 * su - stale - hop_cost)
    types = 0.26 + 0.30 * sc + 0.28 * su - 0.5 * stale - hop_cost
    anchor = float(np.clip(0.20 + 0.50 * sc + 0.10 * su, 0.0, 1.3))
    degree = float(int(np.clip(1.0 + 60.0 * weight * anchor + rng.normal(0.0, 2.0),
                               0.0, 400.0)))
    resolved = float(rng.random() < p_resolved)
    relation = float(rng.random() < p_relation) if resolved else 0.0
    return {
        "entity_resolved": resolved,
        "relation_present": relation,
        "node_degree": degree if resolved else 0.0,
        "type_coverage": _unit(types + rng.normal(0.0, SD_FEATURE)),
    }


def make_synthetic(n: int, seed: int = 0, *, r_W: float = 0.72, g_W: float = 0.12,
                   r_K: float = 0.93, g_K: float = 0.45, n_traces: int = 10,
                   ghost_confident: float = 0.6) -> list[Record]:
    if n < 0:
        raise ValueError("n must be non-negative")
    rng = np.random.default_rng(seed)
    probes = {"W": _probe_w, "K": _probe_k}
    records: list[Record] = []
    for i in range(n):
        q, distractors = _question(rng, i)
        g_w_eff = float(np.clip(g_W, 0.0, 0.95))
        multiplier = float(STALENESS.get(q.dynamism, 1.0))
        g_k_eff = float(np.clip(g_K * multiplier, 0.0, 0.95))
        settings = {"W": (float(r_W), g_w_eff), "K": (float(r_K), g_k_eff)}
        rec = Record(question=q)
        agent_correct: dict[str, bool] = {}
        confident_ghost: dict[str, bool] = {}
        for source in SOURCES:
            r_s, g_s = settings[source]
            member = bool(rng.random() >= g_s)
            correct = bool(member and rng.random() < r_s)
            run, confident = _run(rng, q.qid, source, q.answer, distractors,
                                  member, correct, n_traces, ghost_confident)
            rec.membership[source] = member
            rec.runs[source] = run
            rec.rho[source] = probes[source](rng, q, member, correct)
            agent_correct[source] = correct
            confident_ghost[source] = confident
        rec.truth = {
            "r_W": float(r_W),
            "g_W": g_w_eff,
            "r_K": float(r_K),
            "g_K": g_k_eff,
            "g_K_base": float(g_K),
            "staleness": multiplier,
            "lambda_W": round((1.0 - g_w_eff) * (1.0 - float(r_W)), 6),
            "lambda_K": round((1.0 - g_k_eff) * (1.0 - float(r_K)), 6),
            "class_W": class_of(rec, "W"),
            "class_K": class_of(rec, "K"),
            "correct_W": agent_correct["W"],
            "correct_K": agent_correct["K"],
            "confident_ghost_W": confident_ghost["W"],
            "confident_ghost_K": confident_ghost["K"],
            "n_traces": int(n_traces),
            "seed": int(seed),
        }
        records.append(rec)
    return records


def write_jsonl(records: Iterable[Record], path: str | Path) -> Path:
    target = Path(path)
    if str(target.parent) not in ("", "."):
        target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for rec in records:
            payload = json.dumps(rec.to_json(), sort_keys=True, ensure_ascii=False)
            handle.write(payload + "\n")
    return target


def read_jsonl(path: str | Path) -> list[Record]:
    records: list[Record] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(Record.from_json(json.loads(line)))
    return records


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    n = int(args[0]) if args else 2000
    target = Path(args[1]) if len(args) > 1 else Path("data/synthetic.jsonl")
    seed = int(args[2]) if len(args) > 2 else 0
    written = write_jsonl(make_synthetic(n, seed=seed), target)
    print(f"Synthesised {n} records to {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
