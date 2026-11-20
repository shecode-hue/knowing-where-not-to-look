"""H2 for the parametric source: predict P-knows from the question text alone."""
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

from wk.baseline_agent import grade

RESULTS = ROOT / "results"
SEED = 0


def knows(rec):
    arm = rec["arms"]["closed_book"]
    texts = [arm["answer"] or ""] + list(arm["sample_texts"])
    return any(grade(t, rec["golds"], rec["q"].text) for t in texts if t)


def main():
    rows = pickle.load(open(RESULTS / "baselines_raw_1.5b.pkl", "rb"))
    for r in rows:
        r["knows"] = knows(r)
    cal = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] != "calibration"]
    y_cal = np.array([r["knows"] for r in cal], dtype=int)
    y_te = np.array([r["knows"] for r in test], dtype=int)
    print(f"{len(cal)} calibration, {len(test)} held out; "
          f"P coverage {np.mean([r['knows'] for r in rows]):.3f}")

    probe = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000,
                        sublinear_tf=True),
        LogisticRegression(max_iter=3000, class_weight="balanced"))
    probe.fit([r["q"].text for r in cal], y_cal)
    p = probe.predict_proba([r["q"].text for r in test])[:, 1]
    auc = roc_auc_score(y_te, p)
    rng = np.random.default_rng(SEED)
    shuf = roc_auc_score(rng.permutation(y_te), p)
    print(f"P, question text alone: AUROC {auc:.3f} (shuffled {shuf:.3f})")
    json.dump({"auroc": float(auc), "shuffled": float(shuf),
               "n_test": len(test),
               "coverage": float(np.mean([r["knows"] for r in rows]))},
              open(RESULTS / "p_probe.json", "w"), indent=2)


if __name__ == "__main__":
    main()
