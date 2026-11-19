# Baselines: what was measured, what it showed

## W and K subgroup, Knowing Where Not to Look

AI, Uncertainty and Simulation, Mauritius, November 2026.
Measured on 500 CRAG questions with a local Qwen2.5-1.5B-Instruct reader.

---

# 1. Why baselines come first

A baseline is the method that already exists and already works. Until it is
measured on the same data, with the same metrics, any new number is
uninterpretable: it cannot be known whether the new method improved anything
or merely confirmed that a hard problem is hard.

The project claims that confidence estimates fail in a particular region. If
standard methods already handle CRAG well, the claim is wrong. Establishing
that required running those methods properly, which means using the library
the field uses rather than writing fresh implementations. The project
specification names LM-Polygraph for exactly this reason: it collects over a
dozen uncertainty-estimation methods behind one interface so that teams do not
re-implement them.

An earlier iteration of this subgroup's work did re-implement semantic
entropy by hand. That version compared answers by their words rather than
their meaning, which understated agreement. The results below use
LM-Polygraph's own implementations throughout.

---

# 2. What was collected

Five hundred questions, each asked of the model in four ways:

| Arm | What it is |
|---|---|
| `closed_book` | no retrieval, the model alone. This is the P source |
| `concat_rag` | all retrieved text in a single prompt. The default production system |
| `w_only` | web passages only |
| `k_only` | knowledge-base facts only |

For every question and arm the following was recorded: the answer, per-token
log-probabilities, ten further answers sampled at temperature 1.0, a
confidence figure the model was asked to state, and P(True).

Questions were divided 40% calibration, 20% development and 40% test,
stratified by domain, question type and dynamism, as the specification
requires. Every estimator was calibrated by isotonic regression on the
calibration split alone and reported on the held-out test split.

---

# 3. The nine estimators

| Estimator | What it computes |
|---|---|
| PTrue | asks the model whether its own answer is correct, and reads the probability of "True" |
| MaximumSequenceProbability | how likely the model considered its own answer |
| MonteCarloSequenceEntropy | the spread of probabilities across the ten samples |
| LexicalSimilarity | how similar the ten samples are, word for word |
| VerbalisedConfidence | the number the model states when asked, from 0 to 100 |
| MeanTokenEntropy | average uncertainty at each token during generation |
| DegMat | graph connectivity over semantic similarity between samples |
| Eccentricity | how far samples sit from the centre of that graph |
| NumSemSets | the number of distinct meanings among the samples |

The final three require a natural-language-inference model, which judges
whether "Nolan" and "Christopher Nolan directed it" express the same answer.
A small DeBERTa entailment model was used for this.

---

# 4. The metrics, and why several are needed

**AUROC** measures ranking alone. Given one correct and one incorrect answer,
it is the probability that the method assigns higher confidence to the correct
one. A score of 0.5 is a coin flip; below 0.5 means the signal is inverted.

**Expected calibration error** measures something different: whether a stated
confidence of 70% corresponds to being right 70% of the time. A method can
rank perfectly and remain badly calibrated.

**The Brier score, decomposed by Murphy**, separates these into *reliability*
(is the confidence calibrated) and *resolution* (does it discriminate at all).
This separation matters because a method can be well calibrated and useless,
or sharp but overconfident, and a single score cannot distinguish them.

**Log score** punishes confident errors most heavily. **Risk-coverage area**
gives the cost of abstaining in order to reach a given error rate.

---

# 5. Results

AUROC by estimator and arm, on 195 held-out questions:

| Estimator | closed | concat | W | K |
|---|---|---|---|---|
| PTrue | 0.837 | 0.806 | 0.805 | **0.977** |
| MaximumSequenceProbability | 0.865 | 0.788 | 0.789 | **0.975** |
| MonteCarloSequenceEntropy | 0.862 | 0.782 | 0.782 | **0.979** |
| LexicalSimilarity | **0.885** | 0.780 | 0.780 | **0.979** |
| VerbalisedConfidence | 0.624 | 0.548 | 0.547 | 0.772 |
| MeanTokenEntropy | 0.294 | 0.240 | 0.240 | **0.034** |
| DegMat | 0.398 | 0.336 | 0.336 | 0.153 |
| Eccentricity | 0.397 | 0.323 | 0.323 | 0.154 |
| NumSemSets | 0.479 | 0.467 | 0.467 | 0.317 |

Accuracy was 0.082 closed-book, 0.164 with web retrieval and 0.092 on the
knowledge base, which answered only 14.9% of questions.

## 5.1 The baselines are strong

Working estimators reach 0.78 to 0.89 on the web and 0.975 to 0.979 on the
knowledge base. It cannot be claimed that standard uncertainty estimation
fails on CRAG, because it does not. Any contribution must therefore be
narrower: identifying the specific region in which these methods break.

## 5.2 The diversity family is inverted

MeanTokenEntropy scores 0.034 on the knowledge base, DegMat 0.153,
Eccentricity 0.154. Scores below 0.5 are worse than chance, and 0.034 is
close to perfectly backwards.

The mechanism is identifiable. When the model abstains, it abstains
consistently, so diversity among its samples collapses. These estimators read
low diversity as confidence. **They cannot distinguish confidently answering
from confidently refusing.**

This matters for any task that permits abstention, and it is consistent with a
separate finding from the agreement experiment, where semantic entropy also
ran below chance at AUROC 0.394.

## 5.3 Source identity dominates

Every working estimator rises from approximately 0.78 on the web to
approximately 0.977 on the knowledge base. The model, the questions and the
method are identical; only the source differs.

Knowledge-graph facts are short, self-contained, and either present or absent.
Web passages are long, partial and contradictory, so the evidence that an
answer is present is correspondingly weaker. This is independent support for
the subgroup's position that sources should not be pooled.

## 5.4 Verbalised confidence is the weakest usable method

At 0.547 to 0.624, the number a model states when asked is substantially less
informative than the probabilities underlying its own generation. This is the
expected result, and it is the method most visible to end users.

---

# 6. Known defects in these results

**The concatenation-RAG arm was not actually measured.** It is identical to
the web-only arm to three decimal places on every estimator. The reader
truncates evidence at six passages, and the arm was constructed with web
passages first, so the knowledge-base half was silently discarded. This arm
requires a rerun.

**The reader is a 1.5-billion-parameter model**, quantised to four bits. It
was selected under bandwidth constraints rather than on merit. All reader
figures should be read as a floor. A 7-billion-parameter model of the same
family is being prepared so that the scaling question can be answered, and in
particular whether the inversion in section 5.2 persists at larger scale.

**Accuracy is low throughout**, between 0.082 and 0.164. Low base rates widen
confidence intervals and make calibration estimates less stable.

**No frontier model comparison exists.** The specification anticipates one
through an API. Without it, every statement about reader capability is bounded
below and not above.

---

# 7. Anticipated questions

**If the baselines reach AUROC 0.98, is the problem not already solved?**

AUROC measures ranking across all questions. H1 concerns calibration within
particular cells: rare entities, recent questions, multi-hop reasoning. A
method can rank well overall while remaining systematically overconfident in
one region. Tested separately, over-confidence does rise with recency:
realtime questions showed a confidence-accuracy gap of 0.248 against 0.097 for
static questions, with non-overlapping bootstrap intervals.

**Is the sub-chance AUROC a sign error?**

No. The convention is that higher values indicate greater uncertainty, and the
sign is reversed to obtain confidence. The inversion is a genuine property
with the mechanism given in section 5.2, and it reproduces across three
independent estimators and a separate experiment.

**Were the library's implementations used, or fresh ones?**

The library's. An earlier hand-written semantic entropy was discarded once the
discrepancy was identified.

**Why such a small model?**

Bandwidth at the time of selection. Every figure is a floor. The
specification's requirement is a small open model run locally so that token
log-probabilities are available, which a hosted API would not expose.

**Why is the knowledge base so much more predictable than the web?**

Its facts are short and self-contained, and presence is close to binary. Web
evidence is long, partial and often contradictory.

**How was overfitting to the test split avoided?**

Stratified 40/20/40 split, isotonic calibration fitted on the calibration
portion only, bootstrap intervals on test figures, and no inspection of test
results during development.

**Why are two arms identical?**

A defect, described in section 6. It is better raised directly than left to be
discovered.

**What is P(True), and why does it perform well?**

The model is asked to judge its own answer, and the probability of the token
"True" is read off. It originates with Kadavath et al. (2022), cited in the
project specification. It performs well because recognising an incorrect
answer is an easier task than generating a correct one.

---

# 8. The position these results support

The defensible claim is not that this subgroup's method outperforms the
standard ones. It is that **the standard methods were measured properly, they
perform better than the project assumed, and two specific failure regions have
been identified**: abstention, where diversity-based estimators invert, and
recency, where over-confidence rises.

That is a narrower claim than the project's original framing, and a more
defensible one.
