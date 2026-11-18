"""Compare span rankers on real CRAG: word overlap, BM25, embeddings, hybrid."""
import argparse
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np
from rank_bm25 import BM25Okapi

from wk import crag
from wk.baseline_agent import grade, score_span

CACHE = ROOT / "results" / "spans_cache.pkl"
OUT = ROOT / "results" / "ranked.pkl"
PREFILTER = 100
RERANK = 30


def tok(text):
    return [t for t in crag._tokens(text) if t not in crag.STOPWORDS]


def zscore(x):
    x = np.asarray(x, dtype=float)
    return (x - x.mean()) / (x.std() + 1e-9)


def load_reranker():
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=192)
    except Exception as exc:
        print(f"reranker unavailable ({type(exc).__name__})")
        return None


def load_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(
            "sentence-transformers/multi-qa-MiniLM-L6-cos-v1")
    except Exception as exc:
        print(f"embedding model unavailable ({type(exc).__name__}); "
              f"falling back to BM25 only")
        return None


def window(spans, i):
    p, s = spans[i]
    if i + 1 < len(spans) and spans[i + 1][0] == p:
        return s + " " + spans[i + 1][1]
    return s


def rank_all(rows, model):
    out = []
    pending = []
    for row in rows:
        spans = row["spans"]
        q = row["q"].text
        if not spans:
            out.append({"jac": [], "bm25": [], "idx": []})
            continue
        texts = [s for _, s in spans]
        jac = np.array([score_span(q, s) for s in texts])
        bm = BM25Okapi([tok(s) or ["_"] for s in texts])
        b = np.array(bm.get_scores(tok(q) or ["_"]))
        keep = np.argsort(-b)[:PREFILTER]
        out.append({"jac": jac, "bm25": b, "idx": keep})
        pending.append((len(out) - 1, q, [window(spans, i) for i in keep]))
    if model is not None:
        model.max_seq_length = 128
        print(f"embedding {sum(len(p[2]) for p in pending)} passages", flush=True)
        qs = model.encode([p[1] for p in pending], batch_size=256,
                          normalize_embeddings=True, show_progress_bar=False)
        flat = [s for p in pending for s in p[2]]
        emb = model.encode(flat, batch_size=256, normalize_embeddings=True,
                           show_progress_bar=False)
        at = 0
        for (k, _, cands), qv in zip(pending, qs):
            e = emb[at:at + len(cands)]
            at += len(cands)
            out[k]["cos"] = e @ qv
            out[k]["emb"] = e
        ce = load_reranker()
        if ce is not None:
            pairs, where = [], []
            for k, q, cands in pending:
                top = np.argsort(-out[k]["cos"])[:RERANK]
                out[k]["ce_j"] = top
                pairs += [(q, cands[j]) for j in top]
                where.append((k, len(top)))
            print(f"reranking {len(pairs)} pairs", flush=True)
            sc = ce.predict(pairs, batch_size=256, show_progress_bar=False)
            at = 0
            for k, m in where:
                out[k]["ce"] = np.asarray(sc[at:at + m])
                at += m
    return out


def pick(row, rk, method):
    spans = row["spans"]
    if not spans:
        return None, 0.0
    if method == "jaccard":
        i = int(np.argmax(rk["jac"]))
        return spans[i][1], float(rk["jac"][i])
    if method == "bm25":
        i = int(np.argmax(rk["bm25"]))
        return spans[i][1], float(rk["bm25"][i])
    idx = rk["idx"]
    if method == "bm25_window":
        i = int(idx[0])
        return window(spans, i), float(rk["bm25"][i])
    if "cos" not in rk:
        return None, 0.0
    cos = rk["cos"]
    if method == "embed":
        j = int(np.argmax(cos))
        return window(spans, int(idx[j])), float(cos[j])
    if method == "hybrid":
        s = zscore(cos) + 0.5 * zscore(rk["bm25"][idx])
        j = int(np.argmax(s))
        return window(spans, int(idx[j])), float(cos[j])
    if method == "rerank":
        if "ce" not in rk:
            return None, 0.0
        j = int(rk["ce_j"][int(np.argmax(rk["ce"]))])
        return window(spans, int(idx[j])), float(np.max(rk["ce"]))
    raise ValueError(method)


def evaluate(rows, ranks, method):
    hit = miss = imposs = 0
    scores, correct, member = [], [], []
    for row, rk in zip(rows, ranks):
        ans, sc = pick(row, rk, method)
        ok = grade(ans, row["golds"], row["q"].text)
        scores.append(sc)
        correct.append(ok)
        member.append(row["member"])
        if row["member"]:
            hit += ok
            miss += not ok
        elif ok:
            imposs += 1
    return {"r": hit / max(hit + miss, 1), "impossible": imposs,
            "scores": np.array(scores), "correct": np.array(correct),
            "member": np.array(member)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    rows = pickle.load(open(CACHE, "rb"))[:args.limit]
    model = load_model()
    ranks = rank_all(rows, model)
    n_member = sum(r["member"] for r in rows)
    print(f"{len(rows)} real questions, answer present in {n_member}")
    print(f"\n{'method':<14}{'r (found when present)':>24}{'impossible':>12}")
    results = {}
    for m in ("jaccard", "bm25", "bm25_window", "embed", "hybrid", "rerank"):
        res = evaluate(rows, ranks, m)
        results[m] = res
        print(f"{m:<14}{res['r']:>24.3f}{res['impossible']:>12d}")
    pickle.dump({"ranks": ranks, "results": results}, open(OUT, "wb"))


if __name__ == "__main__":
    main()
