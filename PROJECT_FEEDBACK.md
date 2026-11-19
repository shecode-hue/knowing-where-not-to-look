# Knowing Where Not to Look

## Progress report from the W and K subgroup

Open web source (W) and curated knowledge base source (K).
AI, Uncertainty and Simulation, Mauritius, November 2026.

---

# 1. The problem being addressed

When a retrieval agent answers incorrectly, there are two distinct causes, and
from the outside they are indistinguishable.

Either the answer was in the source and the agent failed to reach it, which
better retrieval can fix. Or the answer was in no source the agent can reach,
which no amount of better retrieval can fix.

The standard method for estimating confidence makes the second case worse. An
agent is run several times and agreement among its responses is treated as
confidence. When the answer is absent from the corpus, every run reads the
same incomplete sources and returns the same incorrect answer, so agreement is
high precisely where correctness is lowest.

The subgroup's task is to estimate these two causes separately, for each
source, and to predict them before the agent runs.

---

# 2. What has been built

A measurement harness that labels every question, for each source, into one of
three classes: the answer was present and found (covered), present and missed
(rare), or absent (ghost). Counting those classes yields the two quantities:

```
reliability  r = covered / (covered + rare)
ghost mass   g = ghost / all questions
```

The harness has been run on real CRAG data, not simulation: 2,706 questions
for W and 2,706 for K, across all five domains. K is wired to the movie, open,
music, finance and NBA knowledge graphs, totalling 4.3 GB.

The agent has been taken through three generations, each recorded with its
measured effect: keyword overlap, then three-stage semantic retrieval (BM25
shortlist, embedding rank, cross-encoder rerank), then a local language model
that reads the retrieved passages and writes the answer. The language model
also supplies the parametric source (P) at no additional cost, since asking it
without retrieval is exactly what P means.

All 57 papers cited in the landscape survey have been read and compared.

---

# 3. Findings that are well supported

## 3.1 The two quantities are independent

This is the central result. A reasonable objection to the whole project is
that ghost mass and reliability are not two things but one, arbitrarily split,
and that every ghost is merely retrieval failing harder.

The objection is testable. Changing the agent while holding the corpus fixed
produced:

| Agent generation | r (W) | g (W) |
|---|---|---|
| Keyword overlap | 0.066 | 0.318 |
| Semantic retrieval | 0.222 | 0.326 |
| Language model reader | 0.286 | 0.343 |

Reliability rose more than fourfold. Ghost mass did not move beyond sampling
error. Had ghost mass been hard retrieval, a fourfold better retriever would
have reduced it.

The mirror experiment, holding the agent fixed and enlarging the corpus
tenfold, is in progress and described in section 5.

## 3.2 Sources are not interchangeable

W and K differ on every axis measured, which argues against pooling sources or
treating them as exchangeable:

| | W (open web) | K (knowledge base) |
|---|---|---|
| Ghost mass | 0.34 | 0.73 |
| Precision when answering | 0.235 | 0.496 |
| Coverage predictable from the question | no (AUROC 0.51) | yes (AUROC 0.83) |

W usually holds something but is contradictory. K is precise but frequently
holds nothing. The appropriate action differs by source, which a single pooled
confidence cannot express.

## 3.3 Separating the quantities changes the decision

With a reliability-aware abstention threshold fitted on a training half and
applied unchanged to a held-out half, the CRAG score became positive for the
first time, and the rate of answering when the answer was absent fell from
1.00 to approximately 0.02. The agent answers a small fraction of questions.
That is the correct policy under a scoring rule that penalises incorrect
answers equally to rewarding correct ones, not a result to celebrate.

---

# 4. Findings that were not anticipated

## 4.1 The fusion rule in the landscape review cannot answer anything

This requires attention from the fusion subgroup, since it concerns their
stage. The rule given is

```
p(y|e) ∝ p₀(y) · ∏_s [(1−g_s)(r_s p_s + (1−r_s)u(y)) + g_s u(y)]
```

Solving for the condition under which a candidate answer is preferred to
abstention yields

```
answer only if   r_s > g_s / (1 − g_s)
```

For W this requires reliability above 0.58 against a measured 0.286. For K it
requires reliability above 2.76, which no probability can satisfy. The failure
was confirmed empirically rather than inferred: on a probe set K answered
correctly every time it answered, and the rule still silenced it. Every fused
configuration answered zero questions.

The cause is that the term `g_s·u(y)` distributes ghost mass across every
candidate, including the one that source has just proposed. A source that
almost certainly lacks the answer therefore still endorses its own guess.

Two corrections were implemented and verified. Placing ghost mass on the
outside option, where "the answer is in none of these candidates" belongs, and
replacing the product with a noisy-OR over the event that a source both holds
the answer and retrieves it correctly, probability `(1 − g_s)·r_s`. Both pass
every case the original fails: a trustworthy source answers at 0.90, three
mediocre sources that agree answer at 0.73, and a source with high ghost mass
abstains at 0.98.

The error appears to have gone unnoticed because no prior work carries the two
quantities separately through to the decision rule, which is the gap this
project identifies.

## 4.2 The subgroup's own premise required weakening

The project's stated premise is that sampling-based confidence cannot detect
corpus absence. An early measurement appeared to confirm it, showing agreement
of 0.38 against each of the three classes. That measurement used an extractive
agent sampling among five nearly-tied candidate spans, so its agreement
reflected the proximity of those scores rather than any belief, and the result
was not evidence about language-model agents.

Repeating the test with a language model sampling ten times at temperature
0.7, on 300 questions:

| Class | Mean agreement | 95% interval |
|---|---|---|
| Covered | 0.371 | [0.313, 0.435] |
| Rare | 0.252 | [0.212, 0.294] |
| Ghost | 0.195 | [0.144, 0.249] |

The intervals for covered and ghost do not overlap. Agreement predicts
presence at AUROC 0.639 against a permutation baseline of 0.517.

The strong form of the premise is therefore false. Sampling is not blind to
absence. The defensible claim is narrower: the signal is weak, around 0.64,
too weak to rely on alone, which is why separate estimation of ghost mass
remains worthwhile.

Two details refine this. The informative component is the abstention rate
(AUROC 0.629), meaning the model declining to answer, rather than consensus
among the answers it does give. And semantic entropy is inverted on this task
(AUROC 0.394, below chance): when the answer is present the model has several
valid ways to phrase it, so entropy rises. Treating low entropy as confidence
has the sign backwards here.

## 4.3 A third failure class is being miscounted as ghost

In the sports and finance domains the underlying data is present but the
answer must be computed across many records, for example a season average or a
comparison across every company in an index. The membership test asks whether
the gold answer text appears in the retrieved evidence, so a computed answer
never satisfies it and is recorded as a ghost.

The scale is material. 44% of sports questions require aggregation over game
records, and the majority of finance questions require computation across
companies or dates. K found the answer for 0 of 60 sampled sports questions
and 3 of 40 finance questions, despite the NBA graph holding 65,698 games and
3,608 players.

Ghost mass in these domains therefore reflects a capability gap rather than a
corpus deficiency. The honest decomposition is three-way: absent from the
corpus, present but not retrieved, and derivable but never stated. Aggregation,
comparison and post-processing questions should be reported separately from
lookups before any domain-level ghost mass figures are circulated.

## 4.4 Half the original ghost mass was measurement error

The first measurement gave a ghost mass of 0.639 for W, with five logically
impossible cells in the contingency table. Two defects in the subgroup's own
labelling were responsible. The grader credited answers that merely repeated
the question's own entity, and the membership test required a verbatim string
match although 24% of CRAG gold answers are full sentences. Correcting both
moved ghost mass to 0.318.

Approximately half of the ghosts originally reported were artefacts of
measurement. Thirty-five tests now guard the labelling, including runtime
checks that fail if any answer text reaches the probe features.

## 4.5 The parametric source is reliable and cannot assess itself

P is the most reliable source on the questions it covers, with reliability
0.476 against 0.286 for K and 0.138 for W. It covers only 11% of questions,
and it answers 47.8% of them, producing an answer when the answer is absent at
a rate of 0.445.

This is the hallucination failure in measured form. The knowledge is sound and
the self-knowledge is not. A threshold on the model's own token logprobs
corrects it, at the cost of answering almost nothing.

---

# 5. What remains weak, and what would resolve it

## 5.1 The W coverage result may be an artefact

W's probe fails to predict coverage, scoring AUROC 0.51 against a permutation
baseline of 0.500, which is indistinguishable from no signal. However, CRAG
tasks 1 and 2 supply every question with exactly five unscored pages, so the
hit-count probe is a constant by construction.

It is not currently possible to distinguish "open-web coverage is
unpredictable from the question" from "the benchmark removed the only varying
signal". This should not be reported as a finding until resolved.

## 5.2 The second half of the independence experiment

CRAG task 3 supplies fifty pages per question instead of five. Running the
existing agent unchanged against it tests the mirror prediction: ghost mass
should fall while reliability holds approximately steady.

This experiment resolves 5.1 at the same time, since with fifty pages the hit
count genuinely varies. The release is 7.73 GB across four parts and is
downloading. It will be streamed rather than extracted, as available disk is
27 GB and the extracted corpus would exceed that.

## 5.3 Entity resolution is confounded with absence on K

K reports no resolved entity for 36% of questions. The proportion attributable
to the linker failing, as against the graph genuinely lacking the entity, has
not been measured. Ghost mass for K is inflated by an unknown amount until it
is.

## 5.4 The reader is a small model

The language model used is a 1.5-billion-parameter instruct model, quantised
to four bits, run locally. Its reader performance should be read as a floor
rather than a ceiling. Notably, for W it does not beat span selection: the
abstention optimiser silences it at every threshold, whereas the extractive
agent with a fitted threshold scores positively.

---

# 6. Recommendations

**To the fusion subgroup.** The combination rule as published cannot answer.
Adopt either correction in section 4.1 before building on it, and treat
`r_s` and `g_s` as per-question quantities predicted by the probe rather than
marginal rates, since marginal rates silence any source with high ghost mass
regardless of its reliability.

**To the group.** Do not pool sources. Report aggregation and comparison
questions separately from lookups, so that capability gaps are not recorded as
corpus absence. Soften the project's claim about sampling from "cannot detect"
to "detects weakly, via abstention rather than consensus", and note that
semantic entropy is inverted on this task.

**Within the subgroup.** Complete the fifty-page experiment, which closes both
the independence result and the W coverage confound. Measure the entity-linking
component of K's ghost mass. Where a stronger reader becomes available, repeat
the reader comparison, since the current one is a floor.
