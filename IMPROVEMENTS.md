# Agent improvements, recorded

Every change to the agent, what it was measured against, and what it did to
the numbers. All figures are on real CRAG data, never simulated.

## What the columns mean

| Column | Meaning | Direction |
|---|---|---|
| **r** | found the answer, of the questions where the answer was present | higher |
| **g** | answer not in the source at all | fixed by the source, not the agent |
| **ans** | share of questions the agent chose to answer | depends |
| **bluff** | answered anyway, of the questions where the answer was absent | lower |
| **CRAG** | (correct − wrong) / all questions; abstaining scores 0 | higher |

The CRAG score is the headline, because it is the only one that punishes
confident wrong answers. An agent that answers everything badly scores worse
than one that stays quiet.

---

## Version 1. Keyword overlap (the starting point)

Spans scored by the share of words shared with the question, top one returned,
abstain if that share is below 0.18.

| Source | r | g | CRAG |
|---|---|---|---|
| W, 2,706 questions | 0.066 | 0.318 | about −0.79 |
| K, 1,153 questions | 0.164 | 0.640 | not recorded |

**The problem it has:** no shared words means no match. "Who directed
Oppenheimer?" cannot match "the film was helmed by Christopher Nolan".

---

## Version 2. Three-stage semantic ranking

1. BM25 keeps the best 100 passages (fast, good on names and numbers)
2. An embedding model trained on question-to-passage matching keeps 30
3. A cross-encoder reads question and passage together and picks the best

Measured on a 600-question sample of W:

| Ranker | r |
|---|---|
| Keyword overlap | 0.070 |
| BM25 | 0.096 |
| BM25 + next sentence | 0.120 |
| Embeddings | 0.151 |
| Embeddings + BM25 blended | 0.139 |
| **Embeddings + cross-encoder** | **0.267** |

Blending BM25 back in made things worse, so the final pipeline does not do it.

---

## Version 3. Semantic ranking on the full dataset

The three-stage ranker applied to every question in both sources, replacing
keyword overlap. Reliability, with the answer always given:

| Source | Keyword `r` | Semantic `r` | Change |
|---|---|---|---|
| W, 2,706 questions | 0.066 | **0.222** | 3.4 times |
| K, 1,153 questions | 0.164 | **0.632** | 3.9 times |

Ghost mass was unmoved: W 0.318 to 0.326, K 0.640 to 0.646, both within the
sampling interval. **This is the first half of the independence experiment.**
The agent changed, the corpus did not, and `r` rose while `g` stayed put.

K gains far more than W. Knowledge-graph facts are short, self-contained
sentences, which is the input a cross-encoder handles best. Web passages are
long and noisy by comparison.

## Version 4. Calibrated abstention

The agent answers only when confident. The threshold is fitted on a training
half and applied unchanged to a held-out half, so it is measured, not tuned
to the result.

| Version | r | answered | bluff | CRAG |
|---|---|---|---|---|
| W, always answer | 0.222 | 1.000 | 1.000 | **−0.701** |
| W, ranker score threshold | 0.027 | 0.029 | 0.007 | **+0.007** |
| W, confidence model | 0.060 | 0.073 | 0.023 | **+0.008** |
| K, always answer | 0.632 | 1.000 | 1.000 | **−0.553** |
| K, ranker score threshold | 0.368 | 0.212 | 0.031 | **+0.048** |
| K, confidence model | 0.349 | 0.199 | 0.034 | **+0.048** |

**The CRAG score turns positive for the first time.** The bluff rate falls
from 1.00 to 0.02 on W and 0.03 on K.

The cost is coverage. The optimiser answers only 7% of W questions and 20% of
K questions, because at `r = 0.22` an average answer is worth
`0.22 − 0.78 = −0.56`. Staying silent is genuinely the better policy for this
agent, and the optimiser is right to choose it. The remedy is a better agent,
not a looser threshold.

The trained confidence model barely beats a threshold on the ranker score
alone (+0.008 against +0.007 on W, identical on K), so on this evidence the
five extra features are not earning their place.

## The risk and coverage trade-off

Forcing the agent to answer a fixed share of questions, best-first:

| Share answered | W: r | W: CRAG | K: r | K: CRAG |
|---|---|---|---|---|
| 10% | 0.084 | +0.013 | 0.222 | +0.057 |
| 25% | 0.124 | −0.083 | 0.434 | +0.057 |
| 50% | 0.169 | −0.272 | 0.618 | −0.063 |

K sustains 25% coverage at a positive score; W cannot hold 25% without going
negative. This is the clearest single statement of the gap between the two
sources.

## Version 5. Both sources together

| Version | r | g | answered | CRAG |
|---|---|---|---|---|
| W alone, shared questions | 0.071 | 0.350 | 0.081 | +0.011 |
| K alone, shared questions | 0.296 | 0.654 | 0.212 | −0.007 |
| Pick the more confident source | 0.176 | **0.276** | 0.269 | −0.014 |

**Combining the sources lowers ghost mass**, from 0.350 for W alone and 0.654
for K alone to 0.276 together. The answer is present for more questions when
both are consulted, which is the case for keeping sources separate.

**It does not yet raise the score.** Choosing by whichever source reports
higher confidence gives −0.014, below W alone. The two confidence models were
fitted independently and their outputs are not on a common scale, so a
confident K is not comparable to a confident W. This needs the proper fusion
rule, with `r_s` and `g_s` as weights, rather than a maximum over two
uncalibrated numbers. That belongs to the fusion subgroup.

## The ceiling, and why it is not the ranker

Where present answers are lost on W, measured on 1,200 real questions:

| Stage | Still reachable |
|---|---|
| The answer is inside some single passage | 0.64 |
| It survives the BM25 shortlist | 0.51 |
| It reaches the top 5 | 0.30 |
| It is ranked first | 0.14 |

The first line is the binding limit. **36% of present answers are not inside
any single two-sentence passage**, usually because the gold answer is a whole
sentence assembled from several places. No amount of better ranking fixes
that; it needs a model that reads several passages and writes an answer, which
means an LLM.

So the realistic ceiling for this pipeline is around r = 0.6, not 1.0.

---

## Version 6. An LLM reader, and all four sources

A 1.5B instruct model (Qwen2.5, 4-bit, run locally through llama.cpp on
Metal) reads the retrieved passages and writes the answer, instead of a span
being selected. The same model, asked with no retrieval at all, becomes the
P source; a fact store written from confident answers becomes M.

Measured on 763 held-out questions, with weights fitted on a disjoint 763:

| Source | r | precision | g | answered | bluff | CRAG |
|---|---|---|---|---|---|---|
| W alone | 0.138 | 0.235 | 0.343 | 0.384 | 0.302 | −0.203 |
| K alone | 0.286 | **0.496** | 0.734 | 0.153 | 0.059 | −0.001 |
| P alone | **0.476** | 0.110 | 0.890 | 0.478 | 0.445 | −0.374 |
| M alone | 0.000 | 0.000 | 0.995 | 0.118 | 0.113 | −0.118 |

With a CRAG-optimal abstention threshold fitted per source:

| Source | r | precision | answered | bluff | CRAG |
|---|---|---|---|---|---|
| W | 0.000 | — | 0.000 | 0.000 | 0.000 |
| K | 0.128 | **0.619** | 0.055 | 0.007 | **+0.013** |
| P | 0.024 | 1.000 | 0.003 | 0.000 | +0.003 |
| M | 0.000 | — | 0.000 | 0.000 | 0.000 |

### Reading these numbers

**The reader is not worse than span selection, though `r` says it is.**
W's precision when it answers is 0.235, against 0.222 for the extractive
agent. But the reader abstains on 62% of questions, and an abstention counts
against `r` by its definition, `Pr(ŷ = y* | y* ∈ C_s)`. Reporting precision
alongside `r` separates caution from incompetence; `r` alone conflates them.

**K is the strongest source.** Its reader reaches 0.619 precision and a
positive CRAG score. Knowledge-graph facts are short and self-contained,
which suits both the reranker and a small reader.

**W's reader is never profitable at any threshold.** The optimiser sets it to
permanent silence. For W, span selection with a fitted threshold (+0.008)
beats this reader. A 1.5B model is weak; the result is a floor for reader
performance, not a ceiling.

**P is reliable when it knows and cannot tell when it does not.** It is the
most reliable source on the questions it covers, `r = 0.476`, higher than W
or K. But it covers only 11% of questions (`g = 0.890`) and answers 47.8% of
them, bluffing at 0.445. That is the hallucination failure, measured: the
knowledge is good, the self-knowledge is not. A threshold on its own logprob
fixes it, at the cost of answering almost nothing.

**M contributes nothing, as predicted.** Ghost mass 0.995. CRAG questions are
unique, so a memory written during the run has almost nothing to recall. This
is reported rather than concealed; measuring M needs a benchmark with
repeated or related queries.

## The flaw found in the fusion rule

The rule in the landscape review,

```
p(y|e) ∝ p₀(y) · ∏_s [(1−g_s)(r_s p_s + (1−r_s)u(y)) + g_s u(y)]
```

spreads ghost mass `g_s·u(y)` over every candidate, including the one that
source proposed. Solving for when a candidate beats abstention gives

```
answer only if   r_s > g_s / (1 − g_s)
```

W would need `r > 0.58` against an actual 0.138, and K would need
`r > 2.76`, which no source can satisfy. The condition was confirmed
empirically: on a 20-question probe K answered correctly every time it
answered (`r = 1.0`) and the rule still silenced it. **Every fused version
answered 0% of questions.**

It was replaced with a noisy-OR over the event "this source holds the answer
and retrieved it correctly", probability `(1 − g_s)·r_s`:

```
p(c) = [1 − ∏(1 − (1−g_s)r_s)] · ∏(1 − (1−g_s)r_s)
          s backing c              s backing something else
p(∅) = ∏(1 − (1−g_s)r_s)   over every source that spoke
```

This passes each case the product form fails: a trusted source
(`r=.95, g=.05`) answers at 0.90, three mediocre sources that agree answer at
0.73, a hopeless source (`r=.2, g=.9`) abstains at 0.98, and on disagreement
the more reliable source is preferred while the decision still abstains.

**Fusion still abstains on real data, and that is correct.** With per-question
`r` and `g` from fitted probes, the combined `(1−g)r` across W, K and P
reaches only about 0.2, below the 0.5 break-even threshold that CRAG scoring
implies. The rule is working; the sources are too weak to be worth polling
jointly. Fusion should be revisited once a stronger reader lifts the per-source
numbers.

---

## Version 7. The independence experiment, completed

The second half: the agent held byte-identical, the corpus grown tenfold
(CRAG task 3, fifty pages per question), on 738 paired questions.

|  | 5 pages | 50 pages | delta |
|---|---|---|---|
| ghost mass `g` | 0.322 | **0.154** | −0.168, 95% CI [−0.195, −0.142] |
| reliability `r` (members) | 0.236 | 0.228 | −0.008 |

With the first half (three agent generations moved `r` from 0.066 to 0.286
while `g` stayed within 0.32 to 0.34), this is a double dissociation: each
manipulation moves exactly one quantity. `r` belongs to the agent, `g` to the
corpus.

Validity check: membership flips were gained 124, lost 0. The small corpus is
a subset of the large one, so a sound labeller can only gain members; a
single loss would have indicated labelling noise.

### The realtime surprise

| dynamism | n | g, 5 pages | g, 50 pages |
|---|---|---|---|
| static | 403 | 0.303 | 0.164 |
| slow | 156 | 0.269 | 0.115 |
| fast | 98 | 0.357 | 0.204 |
| realtime | 81 | 0.481 | **0.123** |

At shallow depth, realtime questions look ghost-heavy and the natural reading
is staleness. At depth they are the best-covered class. The web source's
apparent staleness was substantially a retrieval-depth effect: the fresh
figures exist further down the ranking. Ghost mass as a function of recency is
depth-dependent, which refines the specification's working hypothesis.

### H2 on W, resolved

With fifty pages the retrieval features vary, and membership becomes
predictable at AUROC 0.651 against a shuffled 0.484, above the 0.6 bar. The
earlier null (0.51) was an artifact of every question carrying exactly five
unscored pages. H2 now holds on both sources: K 0.83, W 0.65.

### The window decomposition of rare-passage mass

The agent's 400-span window reaches 62% of member questions; within the
window, r is 0.312, higher than at five pages. The flat overall r is entirely
window truncation: rare-passage mass now separates into answers beyond the
agent's view (38% of members) and answers mis-ranked within it.
