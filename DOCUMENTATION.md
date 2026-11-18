# Knowing Where Not to Look: W and K subgroup

Complete technical record. What the problem is, what the equations say, what
the code does, what has been run, and what is still missing.

Workshop: AI, Uncertainty & Simulation, Tamassa, Mauritius, 16 to 20 November
2026. Project lead: Yabebal Fantaye.

---

# Part 1. The problem

## 1.1 Two failures that look identical from outside

An agent answers a question and is wrong. There are two completely different
reasons, and almost every existing system conflates them.

**Rare passage.** The answer exists in the source. The agent took a route that
missed it. The remedy is engineering: better retrieval, better routing, more
attempts.

**Ghost.** The answer exists nowhere the agent can reach. There is no remedy.
Run it a thousand times and every run confidently returns the nearest thing
that *was* written down, usually last year's figure or a neighbouring entity.
More sampling makes this worse, because agreement rises while correctness
stays at zero.

Telling these apart **before the agent runs** is the project.

## 1.2 Why agreement is not confidence

Self-consistency and semantic entropy run the agent N times and count how
often the answers agree:

```
ĉ_agree(y) = (1/N) Σ_i 1{y(τ_i) = y},      τ_i ~ Q(· | q)
```

As N grows this converges to

```
ĉ_agree(y) → Q(y | q)
```

which is **the agent's own habit**, not the probability that y is correct. The
two coincide only where the proposal Q matches the target P*. This is the
classic importance-sampling failure: when the proposal misses where the target
lives, every sample can agree on a wrong answer while the variance looks
healthy.

The landscape review notes this phenomenon is documented under other names:
CHOKE (Simhi et al., EMNLP 2025), "stubborn hallucinations", Semantic Energy.
What is new here is framing it as a proposal-versus-target mismatch and naming
the two remedies separately.

---

# Part 2. The formalism

## 2.1 Sources and corpora

Four sources: **P** parameters (what the model learnt in training), **W** the
open web plus the user's own turns, **K** a curated knowledge base, **M** the
agent's own memory.

Each source s returns evidence e_s and a distribution over answers
`p_s(y | q, e_s)`. Critically, **a source can only be right about answers its
corpus C_s expresses.**

This subgroup owns **W and K**.

## 2.2 The three quantities we estimate

**Ghost mass.** The probability the answer is not in the corpus at all:

```
g_s(q) = Pr( y* ∉ C_s | φ(q) )
```

Sampling cannot reduce this term. Only another source can.

**Reliability.** Given the answer *is* present, how often the agent gets it:

```
r_s(q) = Pr( ŷ_s = y* | y* ∈ C_s , φ(q) )
```

Note the conditioning. This is not accuracy. It is skill when the agent had a
fair chance.

**Rare-passage mass.** The complement of reliability:

```
λ_s = 1 - r_s
```

It earns a separate name because its remedy differs. In the project's more
general form it is the weight of correct routes the agent samples with
probability below ε:

```
λ_ε(q) = P*( { τ : Q(τ | q) < ε } )
```

## 2.3 Why r and g must never be merged

| Observation | Diagnosis | What to do |
|---|---|---|
| low `r` | you are using this source badly | fix retrieval |
| high `g` | this source cannot help | go elsewhere, or abstain |

Collapse them into one confidence number and the diagnosis is no longer
recoverable, so the action is no longer determined. This is the paper's core
argument.

## 2.4 The KAP prior

Features read from the question **before execution**:

```
φ(q) = ( ω, ρ_P, ρ_W, ρ_K, ρ_M, d )
```

- `ω` ambiguity: is the question well posed, is the premise false
- `ρ_s` how dense and how contested the information is in source s
- `d` inferential distance: hops from evidence to answer

**φ(q) is a prior**, and specifically a prior over *how much to trust each
source*, not over the answer. The agent's run supplies the likelihood. Fusion
gives the posterior. Technically it is an empirical prior conditioned on
covariates: prior with respect to this run, posterior with respect to the
training corpus it was fitted on.

## 2.5 Fusion (the other subgroup's stage, shown for context)

Bayesian noisy channel with an outside option ∅ carrying the ghost mass:

```
p(y | e) ∝ p₀(y) ∏_s [ (1-g_s)( r_s p_s(y|q,e_s) + (1-r_s) u(y) ) + g_s u(y) ]
```

Each source is right with probability `r_s` and emits noise `u` otherwise.
`r_s` and `g_s` are exactly what this subgroup produces. **They are the
weights that decide how loudly each source speaks.**

## 2.6 Hypotheses

- **H1** Agreement is over-confident exactly where answers are hard to reach.
- **H2** The question alone indicates where not to look. *Refuted if AUROC < 0.6.*
- **H3** Keeping sources separate reduces confident wrong answers.
- **H4** Coverage holds in the groups where it matters.

H1 and H2 need only a benchmark and an open model, and the project states they
already constitute a publishable result.

---

# Part 3. The measurement

Everything reduces to one 2×2 per source. For each question, two yes/no
questions: was the answer in this source, and did the agent get it.

|  | agent correct | agent wrong or abstained |
|---|---|---|
| **answer ∈ C_s** | covered | **rare** (λ) |
| **answer ∉ C_s** | *impossible* | **ghost** (g) |

```
r      = covered / (covered + rare)
λ      = rare    / (covered + rare)
g      = ghost row / everything
```

**The impossible cell is a free bug detector.** The agent scoring correct on a
question labelled "answer absent" means one of: wrong membership labels, a
leak between sources, or a grader rewarding a lucky guess. It must be printed
on every run, never silently dropped.

## 3.1 Intervals

Percentile bootstrap, resampling **records** rather than cells, so each
question contributes to exactly one cell and the dependence is respected.

Deliberately **not** a normal approximation. The landscape review cites
*"Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints"*
(arXiv 2503.01747), and per-stratum counts here are small.

---

# Part 4. The code

```
crag.py           load questions, retrieve evidence
    ↓
probes.py         STAGE 1   cheap features, never sees an answer
    ↓
crag.py           STAGE 2   is the gold answer in this evidence?
    ↓
baseline_agent.py STAGE 3   what does a minimal agent say?
    ↓
estimators.py     STAGE 4   the 2×2 → r, g, λ
    ↓
classmodel.py     H2        can stage 1 alone predict the class?
```

## 4.1 `wk/contract.py`

The shared schema. `Question`, `Evidence`, `SourceRun`, `Record`, and
`class_of()` which maps a record to covered/rare/ghost. Also the `Source`
protocol that W and K both satisfy. Everything imports from here.

`SourceRun.majority_correct` scores the agent's *committed* answer, taking the
modal non-abstained trace. Abstentions never count as correct.

## 4.2 `wk/probes.py` — stage 1

**`probe_web`** returns `n_hits`, `agreement_at_10`, `contradiction_rate`,
`recency_spread_days`.

Agreement uses token Jaccard after normalisation:

```
agreement_kernel(a,b) = |tokens(a) ∩ tokens(b)| / |tokens(a) ∪ tokens(b)|
```

The design point: **high `n_hits` with low `agreement_at_10` is the signature
of a contested question**, which is exactly where an agent sounds certain and
is wrong. Topical relevance is not answer-bearingness, so hit count alone must
never stand in for ρ_W.

**`probe_kb`** returns `entity_resolved`, `relation_present`, `node_degree`,
`type_coverage`.

`entity_resolved` and `relation_present` are kept strictly separate. An
entity-linking failure is indistinguishable from genuine absence if they are
merged, and merging them inflates `g_K`, which drives the abstain decision.

`type_coverage` separates "this entity has a gap" from "the graph does not
track this kind of fact for anyone".

**Thresholds are module constants fixed once**, never fitted on evaluation
data: `RELEVANCE_THRESHOLD = 0.35`, `CONTRADICTION_THRESHOLD = 0.2`.

## 4.3 `wk/crag.py` — the adapter, and stage 2

`load_crag()` maps CRAG's fields onto `Question`: `query → text`,
`static_or_dynamic → dynamism`, and so on, tolerantly with `.get()` because
releases differ between tasks.

`CragWebSource` wraps the five retrieved pages (W). `CragKBSource` wraps the
knowledge graph (K).

`contains_answer()` is **stage 2 and the only place the gold answer may be
read.** It checks normalised token containment against the primary answer *and
every entry in `alternative_answers`*, which matters: checking only the primary
would mark a question "absent" when a valid alternative is present, inflating
ghost mass.

## 4.4 `wk/baseline_agent.py` — stage 3, no API key

The project assumes an LLM behind each source. There is no API key here, so
without a substitute the "did the agent get it" axis is unobtainable and there
is no 2×2 at all.

So: a **minimal extractive agent**. Split evidence into sentence-like spans,
score each against the question by lexical overlap, sample `n` traces from the
top-k proportional to score, abstain entirely when the best score falls below
`SCORE_THRESHOLD`.

This is a legitimate minimal agent in the project's sense. **λ measured
against it answers a real question: how often is the answer sitting in the
retrieved pages while a simple pipeline fails to surface it.** That is rare
passage for this proposal Q.

The grader and `contains_answer` must share a normaliser. If they disagree,
the impossible cell fills with artefacts of our own code rather than real
problems.

## 4.5 `wk/estimators.py` — stage 4

`two_by_two`, `estimate_r/g/lambda` returning `(value, lo, hi, n)`,
`bootstrap_ci`, `by_stratum` for splitting by dynamism or domain, and
`summary_table`.

Returns `nan` with `n=0` on an empty denominator rather than raising, because
per-stratum cells legitimately empty out.

## 4.6 `wk/classmodel.py` — the H2 test

StandardScaler plus multinomial logistic regression, `class_weight="balanced"`.
Deliberately small and interpretable: this is a probe-quality test, not a
modelling contest.

`cross_val_auroc` gives one-vs-rest AUROC per class plus macro, from
StratifiedKFold out-of-fold predictions.

**`permutation_baseline` is the part that makes the number mean something.**
It shuffles the labels, refits, and builds a null distribution. Without it,
an AUROC of 0.63 on a small imbalanced sample is indistinguishable from noise.

## 4.7 `wk/simulate.py` — the validation instrument

Generates questions with **known** `r` and `g`. Its only purpose is to prove
the estimators are correct, which cannot be done on real data because nobody
knows the truth there.

It also models staleness explicitly: `g_K` is multiplied by
`{static 0.6, slow 1.0, fast 1.8, realtime 2.4}` and clipped, while `g_W` is
unaffected by dynamism. A knowledge-graph snapshot goes stale; a web index
does not.

---

# Part 5. What has actually been run

## 5.1 Estimator recovery, simulated, 4000 questions

| | estimate | 95% interval | truth |
|---|---|---|---|
| `r_W` | 0.720 | [0.705, 0.735] | 0.720 |
| `g_W` | 0.120 | [0.111, 0.131] | 0.120 |
| `r_K` | 0.926 | [0.916, 0.937] | 0.930 |
| `g_K` | 0.450 | [0.434, 0.465] | 0.450 |

Recovered to three decimals, intervals cover. **This is the proof the
arithmetic is right.**

## 5.2 Staleness, simulated

| dynamism | `g_W` | `g_K` |
|---|---|---|
| static | 0.120 | 0.191 |
| slow | 0.125 | 0.366 |
| fast | 0.117 | 0.546 |
| realtime | 0.121 | **0.714** |

`g_K` nearly quadruples, `g_W` does not move, intervals do not overlap.

## 5.3 H2, simulated

Macro AUROC 0.762 (W) and 0.805 (K) against a permutation null of ~0.497,
p = 0.0099. Ghost is the easiest class (0.86, 0.89), rare the hardest
(0.63, 0.65).

**Interpretation:** the probes are good at *"is it there"* and poor at *"will
we find it"*. That is the right way round, because ghost-versus-not is the
decision that matters: abstain versus try.

## 5.4 Tests

73 passing. Three suites: estimator recovery against known truth, label
leakage (mutation, AST closure, runtime tripwires), and class-model honesty.

## 5.5 Real data, in progress

CRAG task 1/2 v5, **739,310,088 bytes, `bzip2 -t` verified**. 4,409 questions
with five retrieved pages each.

Early diagnostics from the real W run, 120 questions:

```
answer present in evidence   46
survived span splitting      42
ranked in top 5              16
ranked top 1                  6
```

So `r_W ≈ 0.13` for the lexical extractor, hence `λ_W ≈ 0.87`. Low, and
honest. A naive proposal misses most answers that are present. **Rare passage,
not ghost, will dominate this run.**

---

## 5.6 Real data, W, full CRAG task 1/2 v5 (2,706 questions)

First run gave g_W = 0.639 with 5 impossible cells. Both were bugs: the
grader credited predictions that merely repeated the question's entity, and
membership demanded verbatim matches although 24% of gold answers are full
sentences. Fixed in one shared function, `crag.answer_present`: answer words
are the gold's content words minus the question's own words, and 80% must
appear. Corrected run:

| | value | 95% interval |
|---|---|---|
| r_W | 0.066 | [0.055, 0.077] |
| g_W | 0.318 | [0.300, 0.336] |
| λ_W | 0.637 | [0.619, 0.656] |
| impossible | 0 | |

g_W by dynamism: static 0.318, slow 0.244, fast 0.337, **realtime 0.453**.
Highest by domain: finance 0.439.

H2 on W: macro AUROC 0.507 against a null of 0.498, p = 0.26. **Refuted on
this data.** Expected: task 1/2 hands every question exactly 5 unscored pages,
so `n_hits` is the constant 5.

# Part 6. The data

**CRAG**, Comprehensive RAG Benchmark, Meta Reality Labs / FAIR / HKUST,
arXiv 2406.04744, CC BY-NC 4.0. Chosen because it puts W and K behind the
*same* questions, which no other benchmark does.

4,409 questions, 5 domains, 8 question types, popularity head/torso/tail,
dynamism from years to seconds.

**W** comes from `search_results` in the jsonl: five pages each with
`page_name`, `page_url`, `page_snippet`, `page_result` (raw HTML),
`page_last_modified`.

**K** is *not* in the jsonl. It lives in `mock_api/cragkg/`, normally served
by `server.py` over HTTP.

### How K was actually obtained

The HTTP route failed: `pip install -r requirements.txt` died twice on a flaky
connection, the second time building `sqlitedict`, so fastapi never installed.

`cragapi/movie.py` turns out to need only **numpy, loguru and rank_bm25**. So
`MovieKG` is imported and called directly. Same class, same BM25 lookups, no
HTTP hop. `server.py` is a thin FastAPI wrapper around exactly these objects,
so swapping back later is a one-line change.

Downloaded and verified: movie (235 MB, three JSON files) and open (44 MB, two
bz2 archives). Skipped: finance, music, sports, 4.3 GB, with `nba.sqlite`
alone at 2.9 GB.

**This matters for the dynamism test.** Finance and sports are where the
fast-changing questions live. Movie and open are mostly static, so this first
real run can produce `r` and `g` but cannot yet test staleness. Finance costs
about 182 MB if its 717 MB price table is skipped, and is the next thing to
add.

### A warning earned the hard way

Three separate downloads reported success while delivering truncated files:
CRAG at 217 MB of 739, the movie KG at 153 MB of 189, pip at 8.4 MB of 10.8.
`curl` exited **zero** on a corrupt archive.

**Verify bytes, not exit codes.** `bzip2 -t` caught all of them.

---

# Part 7. What is not done

1. **No LLM agent.** Stage 3 is a lexical extractor. Real `r` will rise
   substantially with a real model, and `λ` will fall. `g` should not move,
   and **checking that it does not is itself a result.**
2. **K not yet in a full run.** The graph answers queries; it is not yet
   wired through `run_real.py`.
3. **Finance, music and sports domains absent**, so staleness is untested on
   real data.
4. **Fusion and the decision rule** are stages 5 and 6, the other subgroup's.
   This package hands them `r` and `g`.
5. **No conformal calibration** yet. That is H4.

---

# Part 8. Tools used

| Tool | For |
|---|---|
| numpy, pandas | arrays and tables |
| scikit-learn | logistic regression, StratifiedKFold, AUROC |
| matplotlib | figures |
| rank_bm25 | BM25 inside CRAG's knowledge graph |
| loguru | CRAG's own logging |
| pytest | the 73 tests |
| bz2, json | reading CRAG releases without decompressing |

Deliberately **not** used: transformers, sentence-transformers, any neural
retriever. Everything runs offline on CPU with no API key, which is what makes
the harness reproducible by anyone in the group today.
