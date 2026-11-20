# Model guide

Source-resolved, pre-execution confidence for the web (W) and a curated
knowledge base (K).

This document sets out the problem, the gap in the existing literature, the
formalism, the quantities being estimated, and the method by which an agent's
uncertainty is computed from its responses.

AI Uncertainty & Simulation, Mauritius, November 2026.

---

# Part 1. The problem

When an agent answers a question incorrectly, there are two distinct causes,
and they are indistinguishable from the outside.

**Rare passage.** The answer is present in the source, but the agent followed
a route that failed to reach it. This is remediable through better retrieval.

**Ghost.** The answer is present in no source the agent can reach. No action
by the agent remedies this. Each run returns the nearest answer that was
written down, commonly a superseded figure.

Confidence is conventionally estimated by running the agent N times and
measuring agreement among the responses. On a ghost question every run may
agree on the same incorrect answer, so this estimate is at its most confident
precisely where it is least correct.

**The claim under test:** these two causes must be estimated separately, for
each source, and predicted before the agent is run.

---

# Part 2. The gap

A review of all 57 papers cited in the project's landscape survey (see
`papers/PAPER_REVIEW.md`) identifies four omissions common to every one.

**1. Corpus coverage is not separated from retrieval reliability.**
Sufficient Context (Joren et al., ICLR 2025) estimates the former. RA-RAG
(EMNLP 2025) estimates an approximation of the latter. ERA and EvidentialRAG
combine both into a single evidence score. Once combined, the diagnosis is
unrecoverable: it cannot be determined whether the pipeline or the source is
at fault.

**2. Pre-execution prediction is confined to parametric knowledge.**
Query-Level Uncertainty (ICLR 2026) predicts whether the model itself knows an
answer before generation. No work predicts whether an external corpus, web or
knowledge base, contains it.

**3. A curated store is not distinguished from the open web.**
RA-RAG accommodates multiple sources but treats them as exchangeable.

**4. The independence of the two quantities is unverified.**
No paper varies the agent while holding the corpus fixed, or the converse.

## Remediation

| Gap | Approach | Status |
|---|---|---|
| 1 | Carry `g` and `r` as separate per-source quantities through to the decision rule | Implemented for both sources |
| 2 | Probe features derived solely from the question and the retrieval, never from an answer; evaluated by AUROC | Supported on both sources: K 0.83, W 0.65 once the corpus varies. The earlier W null (0.51) was an artifact of every question carrying exactly five unscored pages |
| 3 | Separate W and K implementations with distinct probe sets | Implemented |
| 4 | Vary the agent with the corpus fixed, and the corpus with the agent fixed | Complete, both directions. Agent varied: `r` 0.066 to 0.286, `g` flat. Corpus grown tenfold on 738 paired questions: `g` 0.322 to 0.154 (CI [-0.195, -0.142]), `r` moved 0.008 |

---

# Part 3. The formalism

## 3.1 The three quantities

For a source `s` with corpus `C_s`, question `q`, true answer `y*`, and agent
response `ŷ_s`:

```
g_s(q) = Pr( y* ∉ C_s | φ(q) )                   ghost mass
r_s(q) = Pr( ŷ_s = y* | y* ∈ C_s , φ(q) )        reliability
λ_s    = 1 − r_s                                  rare-passage mass
```

The conditioning is material. `r` is not accuracy; it is the agent's
performance on the subset of questions where the answer was available.

In practice these are estimated by counting a 2×2 contingency table over real
questions:

```
r = covered / (covered + rare)
λ = rare    / (covered + rare)
g = ghost row / all questions
```

## 3.2 The rationale for separation

```
low r   →  the source holds the answer and retrieval is failing  →  repair the pipeline
high g  →  the source does not hold the answer                   →  change source or abstain
```

A single scalar confidence cannot distinguish these cases and therefore cannot
determine the appropriate action.

## 3.3 The KAP prior

Features computed before the agent is run:

```
φ(q) = ( ω , ρ_P , ρ_W , ρ_K , ρ_M , d )
```

where `ω` denotes how well posed the question is, `ρ_s` the density and
contestedness of information in source `s`, and `d` the number of inferential
hops required.

**φ(q) constitutes a prior over the trustworthiness of each source**, not over
the answer. The implementations are:

```
ρ_W = ( n_hits , agreement@10 , contradiction_rate , recency_spread )
ρ_K = ( entity_resolved , relation_present , node_degree , type_coverage )
```

## 3.4 Fusion

```
p(y | e) ∝ p₀(y) · ∏_s [ (1 − g_s)( r_s p_s(y|q,e_s) + (1 − r_s) u(y) ) + g_s u(y) ]
```

Each source is correct with probability `r_s` and emits noise `u` otherwise.
The outside option `∅`, denoting "none of the candidates", carries the ghost
mass. **`r_s` and `g_s` are the weights**, and constitute this subgroup's
deliverable to the fusion stage.

## 3.5 The decision rule

```
answer ŷ   if  p(ŷ | e) > 1/2
ask        if  the question is ambiguous
abstain    otherwise
```

One half is the optimal threshold under the CRAG scoring rule, in which a
correct answer scores +1, an incorrect answer −1, and an abstention 0.
Answering is favourable exactly when `p·(+1) + (1−p)·(−1) > 0`, that is when
`p > 1/2`.

---

# Part 4. The quantities under optimisation

```
CRAG score = ( correct − wrong ) / all questions
```

| Quantity | Definition | Current (W, real data) | Objective |
|---|---|---|---|
| CRAG score | above | ≈ −0.79 | above 0 |
| Reliability `r` | covered / present | 0.066 → 0.267 | ceiling ≈ 0.6 |
| Rare passage `λ` | 1 − r | 0.93 → 0.73 | decrease |
| Bluff rate | answered / absent | 0.85 | approach 0 |
| Ghost mass `g` | absent / all | 0.318 | **not an agent-side quantity** |
| H2 AUROC | see Part 5 | W 0.51, K 0.83 | above 0.6 |

The CRAG score is the principal measure because it is the only one that
penalises confident incorrect answers. At −0.79 the agent would perform better
by abstaining throughout, which is the failure mode the project addresses.

## Decomposition of reliability, and the ceiling

Measured on 1,200 real W questions in which the answer was present:

```
r = P(a single passage holds it) × P(it survives the shortlist)
    × P(it ranks first) × P(the agent extracts it)

      0.64      ×      0.80      ×      0.28      ×  not yet implemented
```

**The first term is binding.** In 36% of cases the answer is not contained in
any single passage, because the gold answer is frequently a full sentence
assembled from several locations. No improvement in ranking addresses these.
The realistic ceiling for a retrieval-only agent is therefore approximately
**r = 0.6**; exceeding it requires a reader model capable of combining
passages.

---

# Part 5. Estimating uncertainty from agent responses

## 5.1 Prevailing practice and its limitation

The agent is run N times and agreement is counted:

```
ĉ_agree(y) = (1/N) Σ_i 1{ y(τ_i) = y } ,     τ_i ~ Q(· | q)
```

As N increases this converges to `Q(y|q)`, **the agent's sampling
distribution**, not to `Pr(y correct)`. The two coincide only where the
proposal `Q` matches the target `P*`. This is the standard importance-sampling
failure mode.

Semantic entropy refines the measure by clustering the N responses
semantically and taking the entropy of the cluster distribution,

```
H = − Σ_c p(c) log p(c)
```

The limitation is unchanged: it measures dispersion, not correctness.

**Empirical result.** Mean agreement across 10 runs, by outcome:

| Outcome | Mean agreement |
|---|---|
| Answer found (correct) | 0.38 |
| Answer present, not found (incorrect) | 0.38 |
| Answer absent, answered regardless (incorrect) | 0.39 |

The three are indistinguishable. Agreement carried no information about
correctness.

*Qualification: the agent under test samples from its five highest-scoring
candidates, so its agreement largely reflects the proximity of those scores.
The claim concerns LLM agents and requires an LLM for a definitive test.*

## 5.2 Decomposition

For a single source:

```
U_s(q) = U_aleatoric(q)  +  U_parametric(q | s)  +  g_s(q)
```

| Term | Interpretation | Reducible by |
|---|---|---|
| `U_aleatoric` | the question is ambiguous | querying the user |
| `U_parametric` | the source holds the answer but the agent is uncertain | improved retrieval, further sampling |
| `g_s` | the source cannot hold the answer | **no agent-side action** |

The third term is the project's contribution. Sampling cannot detect it,
because every sample is drawn from a corpus that does not contain the answer.

This decomposition should be presented as a reporting convention rather than a
theorem. The landscape review notes that additive decompositions of
uncertainty are formally ill-posed (Kirchhof et al., ICML 2025), so `g_s` is
defined operationally as `Pr(y* ∉ C_s | φ)`, estimated from labelled coverage.

## 5.3 The confidence estimator

The probability is derived not from agreement but from signals produced by the
retrieval stage:

```
P(correct | q, e) = σ( w · φ_conf )

φ_conf = ( ce_top , ce_margin , ce_mean , cos_top , n_cand )
```

`ce_top` denotes the cross-encoder's highest score, `ce_margin` its lead over
the runner-up, and `cos_top` the highest embedding similarity. The weights `w`
are fitted by logistic regression on a training partition, and all results are
reported on a held-out partition.

`ce_margin` carries the most signal: a decisive winner indicates the evidence
isolated a single passage, whereas a flat ranking indicates that no retrieved
passage stands out as an answer.

## 5.4 Verification of calibration

A probability estimate is useful only if calibrated: among cases assigned 0.7,
approximately 70% should be correct.

```
ECE = Σ_b ( n_b / N ) · | accuracy(b) − confidence(b) |
```

Predictions are binned, the stated confidence is compared with observed
accuracy within each bin, and the difference averaged with bin-size weights. A
reliability diagram presents the same quantity graphically. Both are computed
by `wk/classmodel.reliability_curve`.

For the H2 prediction the measure is AUROC, where 0.5 denotes chance,
**reported alongside a permutation baseline** obtained by shuffling labels and
refitting. On real W data the observed score was 0.51 against a shuffled
baseline of 0.50, indicating no signal. On K the observed score was 0.83
against 0.49.

## 5.5 Uncertainty in the estimates themselves

`g = 0.318` derives from a single sample of questions. Resampling the
questions with replacement 5,000 times and taking the central 95% yields:

```
g_W = 0.318 , 95% interval [0.300, 0.336]
```

A bootstrap is used in preference to a normal approximation. The landscape
review cites *Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred
Datapoints* (arXiv 2503.01747), and per-stratum counts here are small.

---

# Part 6. Methods of improvement

| Target | Method | Measured effect |
|---|---|---|
| Increase `r` | Three-stage ranking: BM25 shortlist, embedding rank, cross-encoder rerank | 0.070 → 0.267 on a 600-question W sample |
| Increase `r` further | A reader model combining passages (requires an LLM) | Would address the 36% ceiling |
| Decrease bluff rate | Abstain when `P(correct) < 0.5`, threshold fitted on a training partition | In progress |
| Increase H2 AUROC | Substitute ranker scores for the constant hit count as probes | In progress |
| Decrease `g` | Additional pages per question (CRAG's 50-page release), or a second source | K supplies answers for 6.4% of questions absent from W |

## The experiment establishing independence

One variable is altered at a time, on identical questions:

| Alteration | Prediction | Conclusion if observed |
|---|---|---|
| Improved agent, fixed corpus | `r` rises, `g` unchanged | `r` is a property of the agent |
| Enlarged corpus, fixed agent | `g` falls, `r` approximately unchanged | `g` is a property of the corpus |

Both conditions have now been met. Agent varied, corpus fixed: `r` rose
from 0.066 to 0.286 while `g` stayed within 0.32 to 0.34. Corpus grown
tenfold, agent byte-identical, on 738 paired questions: `g` halved from
0.322 to 0.154 (95% CI on the change [-0.195, -0.142]) while `r` moved by
0.008. Membership flips were 124 gained, 0 lost, the monotonicity a sound
labeller must show. Each manipulation moves exactly one quantity.
