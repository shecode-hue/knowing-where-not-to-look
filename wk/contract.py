"""Shared types for the W and K subgroup; every other module imports these."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Protocol, Any

CLASSES = ("covered", "rare", "ghost")
DYNAMISM = ("static", "slow", "fast", "realtime")
POPULARITY = ("head", "torso", "tail")


@dataclass(frozen=True)
class Question:
    qid: str
    text: str
    answer: str
    domain: str = "unknown"
    question_type: str = "simple"
    dynamism: str = "static"
    popularity: str = "head"
    n_hops: int = 1


@dataclass
class Evidence:
    source: str
    items: list[Any] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceRun:
    qid: str
    source: str
    answers: list[str | None]
    correct: list[bool]

    @property
    def n(self) -> int:
        return len(self.answers)

    @property
    def agreement(self) -> float:
        vals = [a for a in self.answers if a is not None]
        if not vals:
            return 0.0
        return max(vals.count(v) for v in set(vals)) / len(self.answers)

    @property
    def any_correct(self) -> bool:
        return any(self.correct)

    @property
    def majority_correct(self) -> bool:
        vals = [a for a in self.answers if a is not None]
        if not vals:
            return False
        modal = max(set(vals), key=vals.count)
        idx = [i for i, a in enumerate(self.answers) if a == modal]
        return bool(self.correct[idx[0]])

    @property
    def abstained(self) -> bool:
        return all(a is None for a in self.answers)


@dataclass
class Record:
    question: Question
    rho: dict[str, dict[str, float]] = field(default_factory=dict)
    membership: dict[str, bool] = field(default_factory=dict)
    runs: dict[str, SourceRun] = field(default_factory=dict)
    truth: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"question": asdict(self.question), "rho": self.rho,
                "membership": self.membership, "truth": self.truth,
                "runs": {k: asdict(v) for k, v in self.runs.items()}}

    @staticmethod
    def from_json(d: dict) -> "Record":
        return Record(
            question=Question(**d["question"]),
            rho=d.get("rho", {}),
            membership=d.get("membership", {}),
            runs={k: SourceRun(**v) for k, v in d.get("runs", {}).items()},
            truth=d.get("truth", {}))


def class_of(rec: Record, source: str) -> str:
    if not rec.membership.get(source, False):
        return "ghost"
    return "covered" if rec.runs[source].majority_correct else "rare"


class Source(Protocol):
    name: str

    def retrieve(self, q: Question) -> Evidence: ...

    def probe(self, q: Question, ev: Evidence) -> dict[str, float]: ...

    def contains_answer(self, q: Question, ev: Evidence) -> bool: ...

    def run(self, q: Question, ev: Evidence, n: int = 10) -> SourceRun: ...
