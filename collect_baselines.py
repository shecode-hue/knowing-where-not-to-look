"""Collect generations for the specified baselines: greedy, samples, confidences."""
import argparse
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from wk import crag, llm

RESULTS = ROOT / "results"
DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
SEED = 0
CAL, DEV = 0.40, 0.20


def stratified_split(questions):
    buckets = defaultdict(list)
    for q in questions:
        buckets[(q.domain, q.question_type, q.dynamism)].append(q)
    rng = np.random.default_rng(SEED)
    split = {}
    for key, group in buckets.items():
        idx = rng.permutation(len(group))
        n_cal = int(round(CAL * len(group)))
        n_dev = int(round(DEV * len(group)))
        for rank, j in enumerate(idx):
            if rank < n_cal:
                split[group[j].qid] = "calibration"
            elif rank < n_cal + n_dev:
                split[group[j].qid] = "dev"
            else:
                split[group[j].qid] = "test"
    return split


def ranked(row, k=6):
    order = np.argsort(row["ce"])[::-1][:k]
    return [row["texts"][i] for i in order]


def sample_block(question, passages, n, temperature):
    texts, logprobs, means = [], [], []
    width = len(passages) if passages else 6
    for s in range(n):
        out = (llm.read(question, passages, n_evidence=width, seed=s + 1,
                        temperature=temperature) if passages is not None
               else llm.recall(question, seed=s + 1,
                               temperature=temperature))
        texts.append(out["answer"] or "")
        logprobs.append(float(np.sum(out["logprobs"]))
                        if out["logprobs"] else -20.0)
        means.append(out["mean_logprob"])
    return {"sample_texts": texts, "sample_log_probs": logprobs,
            "sample_mean_logprobs": means}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--temperature", type=float, default=1.0)
    args = ap.parse_args()

    llm.start()
    qs = crag.load_crag(DATA)
    w_cache = {r["qid"]: r for r in
               pickle.load(open(RESULTS / "scored_W.pkl", "rb"))}
    k_cache = {r["qid"]: r for r in
               pickle.load(open(RESULTS / "scored_K.pkl", "rb"))}
    pool = [q for q in qs if q.qid in w_cache and q.qid in k_cache]
    split = stratified_split(pool)
    rng = np.random.default_rng(SEED)
    rng.shuffle(pool)
    sample = pool[:args.n]
    counts = defaultdict(int)
    for q in sample:
        counts[split[q.qid]] += 1
    print(f"{len(sample)} questions: " +
          ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), flush=True)

    partial = RESULTS / "baselines_partial.pkl"
    done = {}
    if partial.exists():
        try:
            done = {r["qid"]: r for r in
                    pickle.load(open(partial, "rb"))}
            print(f"resuming: {len(done)} rows already collected",
                  flush=True)
        except Exception:
            done = {}
    rows = [done[q.qid] for q in sample if q.qid in done]
    t0 = time.time()
    for i, q in enumerate(sample):
        if q.qid in done:
            continue
        golds = crag.gold_answers(q)
        w_pass = ranked(w_cache[q.qid])
        k_pass = ranked(k_cache[q.qid])
        both = w_pass[:5] + k_pass[:5]

        rec = {"qid": q.qid, "q": q, "golds": golds,
               "split": split[q.qid], "arms": {}}

        for arm, passages in (("closed_book", None),
                              ("concat_rag", both),
                              ("w_only", w_pass),
                              ("k_only", k_pass)):
            greedy = (llm.read(q.text, passages,
                               n_evidence=len(passages))
                      if passages is not None else llm.recall(q.text))
            block = sample_block(q.text, passages, args.samples,
                                 args.temperature)
            verb = llm.verbalised(q.text, passages)
            rec["arms"][arm] = {
                "answer": greedy["answer"],
                "greedy_log_likelihoods": greedy["logprobs"] or [-20.0],
                "entropy": greedy["entropies"] or [0.0],
                "mean_logprob": greedy["mean_logprob"],
                "abstained": greedy["abstained"],
                "verbalised_answer": verb["answer"],
                "verbalised_confidence": verb["confidence"],
                "p_true": llm.p_true(q.text, greedy["answer"]),
                **block}

        rows.append(rec)
        if len(rows) % 25 == 0:
            tmp = partial.with_suffix(".tmp")
            pickle.dump(rows, open(tmp, "wb"))
            tmp.replace(partial)
        if (i + 1) % 20 == 0:
            rate = (time.time() - t0) / (i + 1)
            print(f"  {i + 1}/{len(sample)}  {time.time() - t0:.0f}s  "
                  f"eta {rate * (len(sample) - i - 1):.0f}s", flush=True)

    llm.stop()
    pickle.dump(rows, open(RESULTS / "baselines_raw.pkl", "wb"))
    partial.unlink(missing_ok=True)
    print(f"\nwritten {RESULTS / 'baselines_raw.pkl'}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
