"""Compare Bayesian fusion with Dempster-Shafer, and their conflict measures."""
import json
import pickle
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import numpy as np
from sklearn.metrics import roc_auc_score

from wk import crag
from wk.baseline_agent import grade

RESULTS = ROOT / "results"
SEED = 0
SOURCES = ("w_only", "k_only", "closed_book")
LABEL = {"w_only": "W", "k_only": "K", "closed_book": "P"}


def norm(text):
    return " ".join(crag._tokens(text)) if text else ""


MEMBER_CACHE = {}


def load_membership():
    for src, name in (("w_only", "W"), ("k_only", "K")):
        path = RESULTS / f"scored_{name}.pkl"
        if path.exists():
            MEMBER_CACHE[src] = {r["qid"]: bool(r["member"])
                                 for r in pickle.load(open(path, "rb"))}


def is_member(r, source):
    cached = MEMBER_CACHE.get(source)
    if cached is not None and r["qid"] in cached:
        return cached[r["qid"]]
    a = r["arms"][source]
    return grade(" ".join(a["sample_texts"]), r["golds"], r["q"].text)


def weights(rows, source):
    member, correct = [], []
    for r in rows:
        member.append(is_member(r, source))
        correct.append(r["arms"][source]["correct"])
    member = np.array(member, dtype=bool)
    correct = np.array(correct, dtype=bool)
    r_val = float(correct[member].mean()) if member.any() else 0.5
    g_val = float((~member).mean())
    return {"r": r_val, "g": g_val, "hit": (1.0 - g_val) * r_val}


def bayes_fuse(said, w, u=None):
    cands = sorted({v for v in said.values() if v})
    if not cands:
        return {None: 1.0}, 0.0
    keys = cands + [None]
    u = u if u is not None else 1.0 / len(keys)
    post = {k: 1.0 for k in keys}
    for src, answer in said.items():
        if not answer:
            continue
        r = w[src]["r"]
        g = w[src]["g"]
        for k in keys:
            if k is None:
                post[k] *= g + (1.0 - g) * (1.0 - r) * u
            else:
                p_s = 1.0 if k == answer else 0.0
                post[k] *= (1.0 - g) * (r * p_s + (1.0 - r) * u)
    z = sum(post.values())
    return ({k: v / z for k, v in post.items()}, z) if z > 0 else \
        ({None: 1.0}, 0.0)


def ds_fuse(said, w):
    focal = {}
    speakers = [(s, a) for s, a in said.items() if a]
    if not speakers:
        return {None: 1.0}, 0.0
    first, answer = speakers[0]
    focal = {answer: w[first]["hit"], None: 1.0 - w[first]["hit"]}
    conflict = 0.0
    for src, ans in speakers[1:]:
        m = {ans: w[src]["hit"], None: 1.0 - w[src]["hit"]}
        combined, kappa = {}, 0.0
        for a_key, a_val in focal.items():
            for b_key, b_val in m.items():
                mass = a_val * b_val
                if a_key is None and b_key is None:
                    tgt = None
                elif a_key is None:
                    tgt = b_key
                elif b_key is None:
                    tgt = a_key
                elif a_key == b_key:
                    tgt = a_key
                else:
                    kappa += mass
                    continue
                combined[tgt] = combined.get(tgt, 0.0) + mass
        conflict = max(conflict, kappa)
        scale = 1.0 - kappa
        focal = ({k: v / scale for k, v in combined.items()} if scale > 1e-12
                 else {None: 1.0})
    return focal, conflict


def ece(conf, correct, bins=10):
    conf = np.clip(np.asarray(conf, dtype=float), 0, 1)
    correct = np.asarray(correct, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if m.sum():
            total += (m.sum() / conf.size) * abs(correct[m].mean()
                                                 - conf[m].mean())
    return float(total)


def crag_score(answered, correct):
    answered = np.asarray(answered, dtype=bool)
    correct = np.asarray(correct, dtype=bool)
    return float((correct.sum() - (answered & ~correct).sum()) / answered.size)


def boot_ci(fn, a, b, reps=2000):
    rng = np.random.default_rng(SEED)
    out = []
    for _ in range(reps):
        idx = rng.integers(0, len(a), len(a))
        try:
            out.append(fn(np.asarray(a)[idx], np.asarray(b)[idx]))
        except Exception:
            continue
    if not out:
        return float("nan"), float("nan")
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def main():
    rows = pickle.load(open(RESULTS / "baselines_raw.pkl", "rb"))
    load_membership()
    for r in rows:
        for s in SOURCES:
            r["arms"][s]["correct"] = grade(r["arms"][s]["answer"],
                                            r["golds"], r["q"].text)
    cal = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] == "test"]
    w = {s: weights(cal, s) for s in SOURCES}
    print(f"{len(cal)} calibration, {len(test)} test")
    print(f"\n{'source':<8}{'r':>7}{'g':>7}{'(1-g)r':>9}")
    for s in SOURCES:
        print(f"{LABEL[s]:<8}{w[s]['r']:>7.3f}{w[s]['g']:>7.3f}"
              f"{w[s]['hit']:>9.3f}")

    report = {"weights": {LABEL[s]: w[s] for s in SOURCES}, "rules": {}}
    for label, subset in (("W+K", ("w_only", "k_only")),
                          ("W+K+P", SOURCES)):
        b_conf, b_ok, b_ans = [], [], []
        d_conf, d_ok, d_ans = [], [], []
        kappas, ratios, contradiction, all_said = [], [], [], []
        for r in test:
            said = {s: norm(r["arms"][s]["answer"]) for s in subset}
            raw = {norm(r["arms"][s]["answer"]): r["arms"][s]["answer"]
                   for s in subset if r["arms"][s]["answer"]}

            post, z_joint = bayes_fuse(said, w)
            named = {k: v for k, v in post.items() if k is not None}
            best = max(named, key=named.get) if named else None
            b_conf.append(named.get(best, 0.0))
            b_ans.append(best is not None and named[best] > 0.5)
            b_ok.append(grade(raw.get(best), r["golds"], r["q"].text)
                        if best else False)

            focal, kappa = ds_fuse(said, w)
            d_named = {k: v for k, v in focal.items() if k is not None}
            d_best = max(d_named, key=d_named.get) if d_named else None
            d_conf.append(d_named.get(d_best, 0.0))
            d_ans.append(d_best is not None and d_named[d_best] > 0.5)
            d_ok.append(grade(raw.get(d_best), r["golds"], r["q"].text)
                        if d_best else False)

            z_sep = 1.0
            for s in subset:
                _, z_s = bayes_fuse({s: said[s]}, w)
                z_sep *= max(z_s, 1e-12)
            all_said.append(said)
            kappas.append(kappa)
            ratios.append(z_joint / z_sep if z_sep > 0 else 0.0)
            spoken = [said[s] for s in subset if said[s]]
            oks = [r["arms"][s]["correct"] for s in subset if said[s]]
            contradiction.append(len(set(spoken)) > 1 and any(oks))

        for name, conf, ok, ans in (("Bayesian", b_conf, b_ok, b_ans),
                                    ("Dempster-Shafer", d_conf, d_ok, d_ans)):
            conf = np.array(conf)
            ok = np.array(ok, dtype=bool)
            ans = np.array(ans, dtype=bool)
            answered = ans
            brier = float(np.mean((conf - ok.astype(float)) ** 2))
            lo, hi = boot_ci(lambda c, y: float(np.mean((c - y) ** 2)),
                             conf, ok.astype(float))
            key = f"{label} {name}"
            report["rules"][key] = {
                "brier": brier, "brier_ci": [lo, hi],
                "ece": ece(conf, ok), "answered": float(answered.mean()),
                "accuracy_when_answering": float(ok[answered].mean())
                if answered.any() else float("nan"),
                "crag": crag_score(answered, ok & answered)}
            print(f"\n{key}")
            print(f"  Brier {brier:.3f} [{lo:.3f}, {hi:.3f}]   "
                  f"ECE {ece(conf, ok):.3f}   answered "
                  f"{answered.mean():.3f}   CRAG "
                  f"{crag_score(answered, ok & answered):+.3f}")

        disagreed = np.array([len({said[s] for s in subset if said[s]}) > 1
                              for r, said in zip(test, all_said)], dtype=bool)
        resolvable = np.array(contradiction, dtype=bool)
        sub_k = np.array(kappas)[disagreed]
        sub_r = np.array(ratios)[disagreed]
        sub_y = resolvable[disagreed].astype(int)
        print(f"\n{label} conflict, among the {int(disagreed.sum())} "
              f"questions where sources disagreed:")
        print(f"  of those, {int(sub_y.sum())} had one source right "
              f"(the rest were all wrong)")
        if 1 < sub_y.sum() < len(sub_y):
            k_auc = roc_auc_score(sub_y, sub_k)
            r_auc = roc_auc_score(sub_y, -sub_r)
            rng = np.random.default_rng(SEED)
            shuf = roc_auc_score(rng.permutation(sub_y), sub_k)
            report["rules"][f"{label} conflict"] = {
                "kappa_auroc": float(k_auc),
                "evidence_ratio_auroc": float(r_auc),
                "shuffled": float(shuf), "n_disagreed": int(disagreed.sum()),
                "n_resolvable": int(sub_y.sum())}
            print(f"  Dempster-Shafer kappa    AUROC {k_auc:.3f}  "
                  f"(shuffled {shuf:.3f})")
            print(f"  Bayesian evidence ratio  AUROC {r_auc:.3f}")
        else:
            print("  too few resolvable disagreements to score")

    json.dump(report, open(RESULTS / "ds_vs_bayes.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'ds_vs_bayes.json'}")


if __name__ == "__main__":
    main()
