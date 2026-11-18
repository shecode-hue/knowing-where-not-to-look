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
