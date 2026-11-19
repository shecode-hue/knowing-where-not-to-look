"""Test whether sampling-based confidence can detect corpus absence."""
import argparse
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from wk import crag, llm
from wk.baseline_agent import grade

RESULTS = ROOT / "results"
DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
SEED = 0


def ranked(row, k=6):
    order = np.argsort(row["ce"])[::-1][:k]
    return [row["texts"][i] for i in order]


def entropy(labels):
    total = len(labels)
    if not total:
        return 0.0
    counts = Counter(labels).values()
    return float(-sum((c / total) * np.log(c / total) for c in counts))


def boot_ci(values, reps=5000):
    if not values:
        return float("nan"), float("nan")
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(SEED)
    draws = rng.choice(arr, size=(reps, arr.size), replace=True).mean(axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--source", default="W")
    args = ap.parse_args()

    llm.start()
    qs = crag.load_crag(DATA)
    cache = {r["qid"]: r for r in
             pickle.load(open(RESULTS / f"scored_{args.source}.pkl", "rb"))}
    pool = [q for q in qs if q.qid in cache]
    rng = np.random.default_rng(SEED)
    rng.shuffle(pool)
    sample = pool[:args.n]
    print(f"{len(sample)} questions, {args.samples} samples each, "
          f"T={args.temperature}", flush=True)

    rows = []
    for i, q in enumerate(sample):
        row = cache[q.qid]
        passages = ranked(row)
        golds = crag.gold_answers(q)
        answers, correct = [], []
        for s in range(args.samples):
            out = llm.read(q.text, passages, seed=s,
                           temperature=args.temperature)
            answers.append(out["answer"])
            correct.append(grade(out["answer"], golds, q.text))

        spoken = [a for a in answers if a]
        norm = [" ".join(crag._tokens(a)) for a in spoken]
        top = Counter(norm).most_common(1)
        agreement = top[0][1] / args.samples if top else 0.0
        member = bool(row["member"])
        majority_right = bool(top) and any(
            c for a, c in zip(norm, correct) if a == top[0][0])

        if not member:
            label = "ghost"
        elif any(correct):
            label = "covered"
        else:
            label = "rare"

        rows.append({"qid": q.qid, "label": label, "member": member,
                     "agreement": agreement,
                     "entropy": entropy(norm),
                     "abstain_rate": 1.0 - len(spoken) / args.samples,
                     "majority_correct": majority_right,
                     "any_correct": bool(any(correct))})
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(sample)}", flush=True)

    llm.stop()
    pickle.dump(rows, open(RESULTS / "agreement.pkl", "wb"))

    print(f"\n{'class':<10}{'n':>5}{'agree':>8}{'95% CI':>18}"
          f"{'entropy':>9}{'abstain':>9}")
    summary = {}
    for label in ("covered", "rare", "ghost"):
        sub = [r for r in rows if r["label"] == label]
        if not sub:
            continue
        ag = [r["agreement"] for r in sub]
        lo, hi = boot_ci(ag)
        summary[label] = {"n": len(sub), "agreement": float(np.mean(ag)),
                          "ci": [lo, hi],
                          "entropy": float(np.mean([r["entropy"]
                                                    for r in sub])),
                          "abstain": float(np.mean([r["abstain_rate"]
                                                    for r in sub]))}
        print(f"{label:<10}{len(sub):>5}{np.mean(ag):>8.3f}"
              f"{f'[{lo:.3f}, {hi:.3f}]':>18}"
              f"{summary[label]['entropy']:>9.3f}"
              f"{summary[label]['abstain']:>9.3f}")

    present = [r for r in rows if r["member"]]
    absent = [r for r in rows if not r["member"]]
    if present and absent:
        from sklearn.metrics import roc_auc_score
        y = np.array([r["member"] for r in rows], dtype=int)
        for name, key in (("agreement", "agreement"),
                          ("negative entropy", "entropy"),
                          ("abstention rate", "abstain_rate")):
            x = np.array([r[key] for r in rows])
            if key == "entropy":
                x = -x
            if key == "abstain_rate":
                x = -x
            auc = roc_auc_score(y, x)
            shuffled = roc_auc_score(
                np.random.default_rng(SEED).permutation(y), x)
            print(f"\nAUROC, {name} predicting answer-is-present: "
                  f"{auc:.3f}  (shuffled baseline {shuffled:.3f})")

    json.dump(summary, open(RESULTS / "agreement.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'agreement.json'}")


if __name__ == "__main__":
    main()
