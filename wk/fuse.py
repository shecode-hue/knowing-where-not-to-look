"""The fusion rule: combine per-source candidates weighted by r_s and g_s."""
from collections import defaultdict

from wk import crag

OUTSIDE = None


def _norm(text):
    return " ".join(crag._tokens(text)) if text else ""


def candidates(proposals):
    groups = defaultdict(list)
    for source, answer, _ in proposals:
        if answer:
            groups[_norm(answer)].append((source, answer))
    return {key: members[0][1] for key, members in groups.items()}


def fuse(proposals, weights, prior=None):
    cands = candidates(proposals)
    if not cands:
        return {"answer": None, "p": 1.0, "posterior": {OUTSIDE: 1.0}}

    said = {}
    for source, answer, _ in proposals:
        if answer:
            said[source] = _norm(answer)

    def hit(source):
        w = weights.get(source, {})
        r = min(max(float(w.get("r", 0.5)), 0.0), 1.0)
        g = min(max(float(w.get("g", 0.5)), 0.0), 1.0)
        return (1.0 - g) * r

    miss_all = 1.0
    for source in said:
        miss_all *= 1.0 - hit(source)

    post = {}
    for key in cands:
        backers = [s for s, a in said.items() if a == key]
        others = [s for s in said if s not in backers]
        support = 1.0
        for s in backers:
            support *= 1.0 - hit(s)
        against = 1.0
        for s in others:
            against *= 1.0 - hit(s)
        post[key] = (1.0 - support) * against
    post[OUTSIDE] = miss_all

    if prior:
        for key in post:
            post[key] *= prior.get(key, 1.0)
    mass = sum(post.values()) or 1.0
    post = {k: v / mass for k, v in post.items()}
    best = max(post, key=post.get)
    return {"answer": cands.get(best) if best is not OUTSIDE else None,
            "p": post[best], "posterior": post}


def decide(result, threshold=0.5):
    if result["answer"] is None:
        return "abstain", None
    if result["p"] > threshold:
        return "answer", result["answer"]
    return "abstain", None
