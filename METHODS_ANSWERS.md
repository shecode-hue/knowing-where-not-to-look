# Methods, answered question by question

Direct answers to the eight questions raised, with the equations, the
concrete examples, and the evidence that every figure comes from executed
runs on real data. File names refer to the public repository
`github.com/shecode-hue/knowing-where-not-to-look`.

---

# 1. What data is used

**Questions.** The CRAG benchmark (Comprehensive RAG Benchmark, Meta,
NeurIPS 2024 Datasets and Benchmarks), public dev split, file
`crag_task_1_and_2_dev_v5.jsonl.bz2`, 739,310,088 bytes on disk, holding
**4,409 questions**. Each record carries: `interaction_id`, the query, the
gold answer with alternates, the domain (finance, sports, music, movie,
open), the question type (simple, simple with condition, comparison,
aggregation, multi-hop, set, post-processing, false premise), a dynamism
label (static, slow, fast, realtime), and **five full web pages** as raw
HTML (`page_result`), returned by CRAG's mock search engine for that query.

**The fifty-page corpus.** CRAG task 3 provides the same questions with
fifty pages each. The first 2,147,483,648 bytes of
`crag_task_3_dev_v5.tar.bz2` were streamed (`extract_task3.py`), yielding
**738 questions** matched by `interaction_id` to the five-page set,
147.6 MB after HTML stripping (`data/task3/task3_matched.jsonl.bz2`).

**The knowledge source K.** CRAG's mock knowledge graphs, downloaded whole:
movie 225 MB, open 42 MB, music 492 MB, finance 868 MB, plus partial
sports. 4.3 GB on disk, served through the benchmark's own loader classes.

**Models.** Readers: `qwen2.5-1.5b-instruct-q4_k_m.gguf` (1,117 MB) and
`qwen2.5-7b-instruct-q4_k_m.gguf` (4,683 MB) under llama.cpp with Metal.
Retrieval: `rank_bm25`, `sentence-transformers/multi-qa-MiniLM-L6-cos-v1`,
`cross-encoder/ms-marco-MiniLM-L-6-v2`. Entailment for the diversity
estimators: `cross-encoder/nli-deberta-v3-small`.

**What is not in any result.** The repository contains a simulator
(`wk/simulate.py`). It was used once, in week one, to unit-test the
estimators by checking they recover a known planted truth. **No reported
number comes from it.** Every figure in the talk traces to cached rows
keyed by CRAG `interaction_id`s.

---

# 2. The estimators, as equations

## 2.1 The project's two quantities

For source `s` with corpus `C_s`, question `q`, true answer `y*`,
pre-execution features `φ(q)`:

```
g_s(q) = Pr( y* ∉ C_s | φ(q) )            ghost mass
r_s(q) = Pr( ŷ_s = y* | y* ∈ C_s, φ(q) )  reliability
```

Estimated by exhaustive counting over questions:

```
r̂ = covered / (covered + rare)        ĝ = ghosts / n
```

**The membership test** (is `y*` in the corpus), `wk/crag.py`: let
`T(y*)` be the gold's content tokens after lowercasing, de-punctuation and
stopword removal, minus tokens already in the question. Then

```
member  ⟺  gold appears verbatim in the corpus token stream
        OR  |T(y*) ∩ corpus tokens| / |T(y*)| ≥ 0.8
```

with every gold alternate tried (`ANSWER_RECALL = 0.8`). Grading of an
agent answer applies the same rule to the answer's tokens, so membership
and correctness share one normalisation.

**The coverage probe** (slide "coverage guessable"): logistic regression

```
P(member | q) = σ( w · φ(q) )
```

with `φ` = TF-IDF of the question text for P; entity-resolved flag, node
degree, type coverage for K; `(ce_top, ce_margin, ce_mean, cos_top,
n_cand, n_spans)` for W. Fitted on one question set, scored on a disjoint
one, reported as AUROC beside a label-shuffled control.

## 2.2 The nine uncertainty estimators

All from LM-Polygraph v0.7.0, fed statistics from our generations. The
generative pieces per question: greedy answer `y` with token logprobs,
ten samples `y₁..y₁₀` at temperature 1.0 (seeds 1 to 10).

```
MaximumSequenceProbability   U = − Σ_t log p(y_t | y_<t, x)

MeanTokenEntropy             U = (1/T) Σ_t H_t ,
                             H_t = − Σ_v p(v) log p(v)
                             (top-5 token distribution from llama.cpp,
                              renormalised)

MonteCarloSequenceEntropy    U = − (1/10) Σ_i log P(y_i | x)

LexicalSimilarity            U = − mean_{i<j} ROUGE-L(y_i, y_j)

Semantic matrix for the next three:
S_ij = P_entail(y_i, y_j) from the NLI model, symmetrised

DegMat                       U = mean_i ( 1 − deg_i / 10 ),
                             deg_i = Σ_j S̄_ij

Eccentricity                 U = ‖ embedding of samples in the graph
                             Laplacian eigenbasis, distance from centroid ‖

NumSemSets                   U = number of equivalence classes under
                             bidirectional entailment above threshold

PTrue                        prompt: "Question … Proposed answer … Is the
                             proposed answer correct? Reply True or False"
                             U = 1 − p("True")   (token probability)

VerbalisedConfidence         prompt asks "CONFIDENCE: <0 to 100>"
                             U = 1 − c/100       (parsed number)
```

Every estimator's raw score is mapped to a probability by **isotonic
regression fitted on the calibration split only**, then scored on the
held-out split: AUROC with a permutation baseline, Brier with Murphy's
reliability–resolution split, ECE, log score, risk–coverage area
(`score_baselines.py`).

---

# 3. What data processing is done

1. **HTML to text** (`wk/crag.py strip_html`): scripts and style blocks
   removed, tags replaced by spaces, entities unescaped, whitespace
   collapsed. Nothing else: no boilerplate removal, no language filter.
2. **Spans** (`wk/semantic_agent.py passages`): each page's text is cut
   into sentence-like spans; consecutive spans are joined pairwise so a
   candidate is roughly two sentences; duplicates removed after
   normalisation; capped at **400 spans per question** (`MAX_SPANS`).
3. **Token normalisation** (`crag._tokens`): lowercase, alphanumerics
   only. Content tokens additionally drop a fixed stopword list.
4. **Knowledge facts**: graph records are rendered as sentences, with
   dates and money spelled in several formats so the membership test is
   fair to K ("2023-07-19", "19 July 2023", "July 19 2023").
5. **Split**: 40% calibration, 20% development, 40% test, **stratified**
   by (domain, question type, dynamism), seed 0
   (`collect_baselines.stratified_split`). Test rows are never touched
   during fitting.
6. Nothing is dropped, rewritten, deduplicated or augmented. K covers the
   four domains whose graphs are wired; that restriction is stated
   wherever K numbers appear.

---

# 4. A concrete corpus enlargement

Enlargement means: for the same `interaction_id`, the five-page evidence
is replaced by the benchmark's fifty-page evidence for that same question.
**Nothing is removed; the five pages are a subset of the fifty.** That
containment gives a built-in validity check: membership can only be
gained. Observed: 124 gained, 0 lost, across all 738 pairs.

A real pair from the run (`show_flip.py` prints these from the caches):

```
interaction_id : ce1ddb48-52c9-4f2d-8968-a4d33bf20525
question       : when did air supply start performing as a band?
gold answer    : 1975
5-page corpus  : member = False   (5 pages, 139 spans; "1975" nowhere)
50-page corpus : member = True    (50 pages; a span contains "1975")
```

The agent that then ranks these spans is byte-identical in both runs.

---

# 5. A concrete agent change

The agent is the retrieval-and-selection policy. The change behind the
"retriever upgraded" bars, with the corpus held at the same five pages:

**Before (A0):** score every span by word overlap with the question,
`|span ∩ query| / |query content tokens|`; answer with the top span;
abstain below 0.18.

**After (A1):** three tools added, nothing else touched:
1. `rank_bm25` BM25Okapi keeps the best **100** spans;
2. the bi-encoder `multi-qa-MiniLM-L6-cos-v1` keeps the top **30** by
   cosine;
3. the cross-encoder `ms-marco-MiniLM-L-6-v2` reads question and span
   together; the answer is its argmax.

Same spans, same membership label, same grading. Result: `r` 0.066 →
0.286, `g` 0.318 → 0.343 (flat within the interval).

**The reader change** (the scaling experiment) swaps one file:
`qwen2.5-1.5b-…gguf` for `qwen2.5-7b-…gguf`. Identical prompts, identical
decoding (greedy at temperature 0, plus ten samples at 1.0, seeds 1 to
10), identical context length.

---

# 6. The pipeline the code implements, step by step

```
 1  load CRAG            wk/crag.py load_crag        4,409 Question objects
 2  retrieve per source  CragWebSource / KBSource    5 or 50 pages; KG facts
 3  strip + span         strip_html, passages()      ≤ 400 candidates
 4  BM25 shortlist       semantic_agent.shortlist    top 100
 5  embed + rank         score_question              top 30 by cosine
 6  cross-encode         score_question              scores for every kept span
 7  cache                score_sources.py            results/scored_W.pkl,
                                                     scored_K.pkl, scored_W50.pkl
 8  label                answer_present, grade       member, correct per row
 9  count                train_agent.py              r̂, ĝ, CRAG score, thresholds
10  probe                run_w50.py, p_probe.py      logistic, AUROC + shuffle
11  read                 collect_baselines.py        4 arms × (greedy + 10
                                                     samples + P(True) +
                                                     verbalised) → baselines_raw.pkl
12  estimate             score_baselines.py          NLI matrices, nine U's,
                                                     isotonic, all metrics
13  decide / fuse        fuse_system.py, conformal.py  thresholds, DS fusion,
                                                     coverage
```

Every stage writes an artifact; every table in the talk is recomputed
from those artifacts by a deterministic script.

---

# 7. "How many times is it measured to compute the graph?"

Each bar in the dissociation figure is **one exhaustive pass over every
question in that condition**, not an average of repeated runs and not a
sample:

- agent arm: 2,706 questions × 2 agents (A0, A1), corpus fixed;
- corpus arm: 738 paired questions × 2 corpora (5, 50 pages), agent fixed.

Decoding in the counting stages is deterministic (greedy, fixed seeds),
so rerunning reproduces the same bars exactly; repetition would add
nothing. The variability that matters is **which questions** were asked,
so the interval is a percentile bootstrap over questions: **5,000
resamples** of the 738 pairs give Δg = −0.168, 95% CI [−0.195, −0.142].
Where sampling exists (the ten generations per question for the
diversity estimators), the counts are stated on the slide: 293 questions
× 10 samples.

---

# 8. Samples per change, and how the model is doing

| measurement | n |
|---|---|
| agent change (A0 vs A1), corpus fixed | 2,706 questions |
| corpus change (5 vs 50 pages), agent fixed | 738 paired questions |
| reader runs (both models) | 500 questions: 207 cal / 98 dev / 195 test |
| estimator study | 293 held-out × 10 samples |
| coverage probes, held out | P 293 · K 576 · W 1,353 · W50 369 |
| fusion calibration comparison | 195 held out |
| real W-against-K disagreements | 70 |

**The model, finished an hour ago (500/500):** the 7B abstains roughly
twice as often as the 1.5B and is 8 to 17 points more precise on every
arm when it answers; raw accuracy barely moves. The entropy inversion
**deepens** at 7B (0.034 → 0.029 on K) and the conditioning repair holds
(0.970). Among the questions the 7B chooses to answer, all nine
estimators fall to chance, so at scale their headline AUROC is abstention
signal only. End to end, oracle routing without abstention scores
−0.056, while every calibrated-abstention variant is positive.

---

# 9. Why this is a run, not a simulation

1. **Artifacts with mass and timestamps.** 739 MB of CRAG, 147.6 MB of
   stripped fifty-page evidence, 4.3 GB of knowledge graphs, 21.4 MB of
   cached W rankings, and wall-clock logs: the 7B collection alone shows
   70,649 seconds of logged progress with 25-row checkpoints.
2. **Traceable identifiers.** Every cached row keys on a CRAG
   `interaction_id` (for example `ce1ddb48-52c9-4f2d-8968-a4d33bf20525`
   above) that can be looked up in Meta's own file.
3. **Determinism on demand.** `python score_sources.py --limit 20` reruns
   the retrieval pipeline on twenty live questions in about two minutes
   and reproduces the cached rows bit for bit.
4. **The one simulator in the repository is quarantined.** `wk/simulate.py`
   exists to unit-test the estimators against a planted truth; it feeds
   no table, and the commit history shows every result landing with its
   generating script.
5. **The repository is public.** Clone it, run stage by stage, and every
   number in the talk falls out.
