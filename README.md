# W and K source harness

Subgroup code for *Knowing Where Not to Look* (Fantaye), AI Uncertainty &
Simulation workshop, Mauritius 2026.

Measures, per source, how often the answer is **not there at all** (ghost mass
`g`), how often the agent **finds it when it is** (reliability `r`), and how
often it **misses something that was there** (rare passage `λ`). Then tests
whether those classes can be predicted from the question alone, before the
agent runs. That last test is hypothesis **H2**.

---

## Run it

```bash
conda activate uncertainty
cd ~/Desktop/knowing_where_not_to_look
python run_demo.py          # end-to-end, prints everything
python -m pytest tests -q   # 73 tests
```

No network needed. No API key needed. No CRAG download needed to start.

---

## Why it runs on simulated data

CRAG is not on this machine, and you cannot validate an estimator against data
whose truth you do not know.

`wk/simulate.py` generates questions with **known** `r` and `g`. You set
`r_K = 0.93`, you run the estimator, and it must give you back 0.93. That is
the only honest way to know the pipeline is correct before real data lands.
When CRAG arrives, swap the loader and nothing else changes.

Current recovery, 4000 questions:

| | estimate | 95% interval | truth |
|---|---|---|---|
| `r_W` | 0.720 | [0.705, 0.735] | 0.720 |
| `g_W` | 0.120 | [0.111, 0.131] | 0.120 |
| `r_K` | 0.926 | [0.916, 0.937] | 0.930 |
| `g_K` | 0.450 | [0.434, 0.465] | 0.450 |

---

## The modules

| File | Does |
|---|---|
| `wk/contract.py` | Shared types. Everything imports these. Do not edit casually. |
| `wk/simulate.py` | Synthetic data with known ground truth |
| `wk/probes.py` | `probe_web`, `probe_kb`. Stage 1. Never sees an answer. |
| `wk/estimators.py` | The 2×2, `r`, `g`, `λ`, percentile bootstrap |
| `wk/classmodel.py` | H2: predict covered/rare/ghost from probes alone |
| `wk/crag.py` | Adapter for real CRAG. `run()` is stubbed, see below. |

---

## Reading the output

**`g`, ghost mass.** How often the answer is simply not in this source.
Sampling cannot reduce it. Only another source can. High `g` means stop asking
this source.

**`r`, reliability.** When the answer *was* there, how often the agent got it.
Low `r` means your retrieval is bad. Fix the pipeline, not the source.

**`λ`, rare passage.** The other half of `r`. It has its own name because it
has its own remedy.

**The `impossible` cell must be zero.** It counts questions where the answer
was labelled absent but the agent scored correct. Non-zero means the
membership labels are wrong, a source leaked, or the grader rewarded a guess.

**`ghost_answered` is the dangerous cell.** The answer was nowhere and the
agent answered anyway. That is the failure the project exists to predict.

**AUROC against the shuffled null.** 0.5 is chance. A score that is not
clearly above the permutation null carries no signal, however large it looks.
H2 is refuted below 0.6.

---

## The central prediction, and it holds

A knowledge graph is a snapshot, so it goes stale. A web index does not.

| dynamism | `g_W` | `g_K` |
|---|---|---|
| static | 0.120 | 0.191 |
| slow | 0.125 | 0.366 |
| fast | 0.117 | 0.546 |
| realtime | 0.121 | **0.714** |

`g_K` nearly quadruples while `g_W` stays flat, with non-overlapping
intervals. That separation is what makes fusing the two sources worth
anything: **two sources that fail identically are worth no more than one.**

---

## What is NOT done

1. **`CragWebSource.run()` and `CragKBSource.run()` raise
   `NotImplementedError`.** The per-source agent needs an API key and belongs
   to stage 3. Everything up to it is finished.
2. **No real CRAG data.** See `wk/crag.DOWNLOAD_HINT`.
3. **No fusion and no decision rule.** Stages 5 and 6 belong to the other
   subgroup; this package hands them `r` and `g`.

---

## The one rule

> **A probe may never see an answer.** Not the gold answer, not a generated
> one, not an answer span.

H2 claims the *question alone* predicts the class. A probe that peeks produces
a beautiful AUROC that means nothing.

`tests/test_no_leakage.py` enforces this with 35 tests: it mutates the gold
answer eight ways and asserts the features come back byte-identical, walks the
call graph with `ast` across three modules, and plants a runtime tripwire that
raises if `.answer` is touched at all. Keep those tests passing.
