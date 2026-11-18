# W and K against the literature, and the way forward

Source: *Knowing Where Not to Look: Landscape Review of Source-Resolved,
Pre-Execution Confidence for Agents* (18 November 2026). Only the papers that
bear on the W and K subgroup are compared here.

---

## 1. The papers, by what they actually do

| Paper | Status | Process | What it estimates in our terms | What it lacks |
|---|---|---|---|---|
| **Sufficient Context**, Joren et al. | ICLR 2025 | An autorater reads the retrieved context and judges whether it is *sufficient* to answer. Errors are split into "context insufficient" versus "model failed to use sufficient context". Sufficiency plus self-rated confidence drives abstention. | **g_W**, the membership label, per retrieval | One source only. No K. No pre-execution prediction. |
| **RA-RAG**, Hwang et al. | EMNLP 2025 | Estimates each source's reliability *offline* by cross-checking sources with fact-checking queries, then retrieves per source and weights answers by reliability. | **r_s** | No ghost mass, no outside option. Treats all external sources as interchangeable web sources, so no W versus K distinction. |
| **ERA**, Shin et al. | preprint, Feb 2026 | Parametric and retrieved representations become separate Dirichlet evidence, fused with Dempster–Shafer; the conflict κ drives abstention. | P versus W fusion with conflict | Two sources only; κ used internally. |
| **EvidentialRAG** | preprint, Jul 2026 | Each retrieved chunk is Dirichlet evidence; a conflict-*preserving* DS operator moves unresolved conflict into uncertainty; routes to answer, conflict-aware answer, or abstain. **On CRAG.** Hallucination 45.3% → 34.8%, ECE 0.122. | Fusion with conflict, on our benchmark | No per-source coverage term, no pre-execution step. |
| **Astute RAG**, **MADAM-RAG** | Google / preprint | Tag passages internal or external; cross-source confirmation as a reliability cue. | Rough r_s | No coverage, no K. |
| **Query-Level Uncertainty**, Chen & Varoquaux | ICLR 2026 | One forward pass, before any token is generated, predicts whether the model can answer. | Pre-execution prediction, parametric only | Predicts *the model*, not *the corpus*. |
| **Moskvoretskii et al.** | ACL 2025 | 27 uncertainty methods against adaptive-retrieval systems; simple signals are competitive. | The baseline suite for H2 | Not source-resolved. |
| **UAEval4RAG**, **RefusalBench** | ACL 2025 / benchmark | Questions built so the answer is known to be *absent* from the corpus. | Ground-truth ghosts for W and K | Benchmarks, not methods. |
| **Kandpal et al.** | ICML 2023 | Accuracy depends causally on how many pretraining documents mention the entity. | ρ_P via popularity | P only. |

## 2. How the processes compare to ours

**Every one of them measures one thing and merges the rest.** Sufficient Context
gets coverage but only for one retrieval. RA-RAG gets reliability but has no
coverage term. ERA and EvidentialRAG get conflict but fold coverage and
reliability into one evidence mass.

Our process is the only one that keeps **coverage g and reliability r as two
separate numbers per source**, and predicts the class **before** the agent
runs. The review says the same: *"None defines a per-source ghost-mass term
g_s that sampling cannot reduce."* And on the subgroup's patch specifically:
*"I found no work that separates a trusted curated store K from the open web
W."*

**Where we are behind them:**

1. **Our membership label is the weakest link, and Sufficient Context is the
   fix.** We decide "the answer is in W" by token overlap. Joren et al. decide
   it with an autorater that reads the context. Our first real run proved the
   point: verbatim matching mislabelled a third of CRAG as ghost because
   those gold answers are whole sentences. Membership is the foundation
   under every number we report.
2. **RA-RAG's cross-checking is a better r estimator than ours** once there are
   enough questions per source, because it does not need a gold answer.
3. **EvidentialRAG already reports on CRAG**, so any CRAG number we publish
   will be read against 34.8%.

**Where we should not compete:** Dempster–Shafer fusion with a conflict score.
Two 2026 preprints do it, one on CRAG. The review calls this the highest
scooping risk. That belongs to the fusion subgroup, and they should lead with
the outside option ∅ and the evidence ratio, which nobody has done.

## 3. The way forward

### 3.1 Fix the foundation: membership

Three tiers, in order of cost:

1. **Now, no key:** the token-recall labeller (answer words minus the
   question's own words, 80% must appear). Done today.
2. **Audit:** hand-label 100 random questions as present or absent. Report
   agreement with the automatic label. Without this, nobody can trust g.
3. **With an API key:** a Sufficient Context-style autorater, validated against
   the same 100 hand labels. Cite Joren et al. as the method.

### 3.2 The experiment that proves the paper's central claim

The paper argues g and r are *independent*: g belongs to the corpus, r to the
agent. Prove it by moving each one while holding the other fixed, on the same
questions.

| Manipulation | Prediction | What it shows |
|---|---|---|
| **Change the corpus**: CRAG task 3 gives 50 pages per question instead of 5 | **g_W falls, r_W roughly unchanged** | g is a property of the corpus |
| **Change the agent**: lexical extractor → LLM | **r_W rises, g_W unchanged** | r is a property of the agent |

If both hold, that is direct empirical evidence for the decomposition no
existing paper has, on the same benchmark EvidentialRAG uses. It also costs
nothing new: task 3 is already in the CRAG release.

### 3.3 Redesign the W probes

On task 1/2 every question gets exactly 5 pages with no relevance scores, so
**`n_hits` is the constant 5** and carries no information. Task 3's 50 ranked
pages fix this, giving real hit counts and a meaningful agreement@10.

### 3.4 Baselines for H2

Run Query-Level Uncertainty and the Moskvoretskii suite on the same CRAG
split. H2 is a claim that *corpus* features beat *model* features at
predicting ghosts, so it must be shown against model-side baselines, not only
against a shuffled null.

### 3.5 Benchmarks for ghosts with known truth

CRAG's absences are inferred. UAEval4RAG and RefusalBench construct questions
whose answers are *known* to be absent, which is the only clean test of ĝ.

### 3.6 Terminology

Map our words onto theirs in the write-up, or reviewers will say we reinvented
them: ghost ↔ "insufficient context" (Joren) and "model-agnostic unknown" (Li
et al.); rare passage ↔ "prompt-sensitive known" and CHOKE; pre-execution
prediction ↔ "query-level uncertainty".
