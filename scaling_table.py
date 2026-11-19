"""Compare every estimator and arm across the 1.5B and 7B readers."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "results"
ARMS = ("closed_book", "concat_rag", "w_only", "k_only")


def load(tag):
    path = RESULTS / f"baseline_scores{tag}.json"
    return json.load(open(path)) if path.exists() else None


def main():
    small = load("_1.5b")
    big = load("")
    if small is None or big is None:
        print("need both baseline_scores_1.5b.json and baseline_scores.json")
        return

    print(f"{'arm':<13}{'acc 1.5B':>9}{'acc 7B':>8}{'ans 1.5B':>10}"
          f"{'ans 7B':>8}")
    for arm in ARMS:
        if arm in small and arm in big:
            print(f"{arm:<13}{small[arm]['accuracy']:>9.3f}"
                  f"{big[arm]['accuracy']:>8.3f}"
                  f"{small[arm]['answered']:>10.3f}"
                  f"{big[arm]['answered']:>8.3f}")

    names = sorted(next(iter(small.values()))["estimators"])
    for metric, label in (("auroc", "AUROC"), ("ece", "ECE"),
                          ("resolution", "resolution")):
        print(f"\n=== {label}, 1.5B -> 7B ===")
        print(f"{'estimator':<28}" + "".join(f"{a[:9]:>19}" for a in ARMS))
        for n in names:
            cells = []
            for a in ARMS:
                s = small.get(a, {}).get("estimators", {}).get(n)
                b = big.get(a, {}).get("estimators", {}).get(n)
                cells.append(f"{s[metric]:>8.3f}->{b[metric]:<6.3f}"
                             if s and b else f"{'-':>15}")
            print(f"{n:<28}" + "".join(f"{c:>19}" for c in cells))

    out = {"arms": {a: {"accuracy": [small[a]["accuracy"],
                                     big[a]["accuracy"]],
                        "answered": [small[a]["answered"],
                                     big[a]["answered"]]}
                    for a in ARMS if a in small and a in big}}
    json.dump(out, open(RESULTS / "scaling.json", "w"), indent=2)
    print(f"\nwritten {RESULTS / 'scaling.json'}")


if __name__ == "__main__":
    main()
