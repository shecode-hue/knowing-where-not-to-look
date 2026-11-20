"""Precision when answering, from the running 7B checkpoint."""
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from wk.baseline_agent import grade

rows = pickle.load(open(ROOT / "results" / "baselines_partial.pkl", "rb"))
old = {"closed_book": 0.157, "concat_rag": 0.260,
       "w_only": 0.258, "k_only": 0.523}
print(f"{'arm':<13}{'prec 7B':>9}{'prec 1.5B':>11}")
for arm in ("closed_book", "concat_rag", "w_only", "k_only"):
    oks = [grade(r["arms"][arm]["answer"], r["golds"], r["q"].text)
           for r in rows if r["arms"][arm]["answer"] is not None]
    prec = float(np.mean(oks)) if oks else float("nan")
    print(f"{arm:<13}{prec:>9.3f}{old[arm]:>11.3f}")
