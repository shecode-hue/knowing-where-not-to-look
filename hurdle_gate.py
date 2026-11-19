"""The hurdle gate: detect ill-posed questions before any source is consulted."""
import json
import pickle
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline

from wk import crag
from wk.baseline_agent import grade

RESULTS = ROOT / "results"
DATA = ROOT / "data" / "crag_task_1_and_2_dev_v5.jsonl.bz2"
SEED = 0


def boot_ci(values, reps=5000):
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(SEED)
    draws = rng.choice(arr, size=(reps, arr.size), replace=True).mean(axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def main():
    w_rows = pickle.load(open(RESULTS / "scored_W.pkl", "rb"))
    k_rows = {r["qid"]: r for r in
              pickle.load(open(RESULTS / "scored_K.pkl", "rb"))}
    rng = np.random.default_rng(SEED)
    idx = rng.permutation(len(w_rows))
    half = len(w_rows) // 2
    train = [w_rows[i] for i in idx[:half]]
    test = [w_rows[i] for i in idx[half:]]

    y_tr = np.array([r["q"].question_type == "false_premise" for r in train],
                    dtype=int)
    y_te = np.array([r["q"].question_type == "false_premise" for r in test],
                    dtype=int)
    gate = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000,
                        sublinear_tf=True),
        LogisticRegression(max_iter=3000, class_weight="balanced"))
    gate.fit([r["q"].text for r in train], y_tr)
    p_te = gate.predict_proba([r["q"].text for r in test])[:, 1]
    auc = roc_auc_score(y_te, p_te)
    shuffled = roc_auc_score(rng.permutation(y_te), p_te)
    print(f"gate detects false premise from the question alone: "
          f"AUROC {auc:.3f} (shuffled {shuffled:.3f}), "
          f"base rate {y_te.mean():.3f} over {len(test)} questions")

    cut = float(np.quantile(p_te, 0.90))
    passed = p_te < cut
    member = np.array([r["member"] for r in test], dtype=bool)

    def g_of(mask):
        return float((~member[mask]).mean())

    oracle = ~y_te.astype(bool)
    g_all = g_of(np.ones(len(test), dtype=bool))
    g_gate = g_of(passed)
    g_oracle = g_of(oracle)
    lo_a, hi_a = boot_ci((~member).astype(float))
    print(f"\nghost mass on W:")
    print(f"  ungated            g = {g_all:.3f}  [{lo_a:.3f}, {hi_a:.3f}]")
    print(f"  learned gate (90%) g = {g_gate:.3f}   "
          f"({(~passed).sum()} questions diverted)")
    print(f"  oracle gate        g = {g_oracle:.3f}   "
          f"({int(y_te.sum())} true false-premise)")
    recovered = (g_all - g_gate) / max(g_all - g_oracle, 1e-9)
    print(f"  the learned gate recovers {recovered:.0%} of the oracle drop")

    k_member = np.array([k_rows[r["qid"]]["member"] for r in test
                         if r["qid"] in k_rows], dtype=bool)
    k_fp = np.array([r["q"].question_type == "false_premise" for r in test
                     if r["qid"] in k_rows], dtype=bool)
    if len(k_member):
        gk_all = float((~k_member).mean())
        gk_gated = float((~k_member[~k_fp]).mean())
        print(f"\nghost mass on K: ungated {gk_all:.3f}, "
              f"oracle-gated {gk_gated:.3f}")

    raw = pickle.load(open(RESULTS / "baselines_raw_1.5b.pkl", "rb"))
    fp = [r for r in raw if r["q"].question_type == "false_premise"]
    ok = [r for r in raw if r["q"].question_type != "false_premise"]
    for arm in ("closed_book", "concat_rag"):
        a_fp = float(np.mean([r["arms"][arm]["answer"] is None for r in fp]))
        a_ok = float(np.mean([r["arms"][arm]["answer"] is None for r in ok]))
        print(f"\nmodel's own abstention on {arm}: "
              f"false-premise {a_fp:.3f} vs well-posed {a_ok:.3f}")

    json.dump({"gate_auroc": float(auc), "shuffled": float(shuffled),
               "g_ungated": g_all, "g_learned": g_gate, "g_oracle": g_oracle,
               "recovered_share": float(recovered)},
              open(RESULTS / "hurdle.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'hurdle.json'}")


if __name__ == "__main__":
    main()
