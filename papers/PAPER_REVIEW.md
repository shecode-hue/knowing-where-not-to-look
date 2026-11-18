# The 57 papers, in plain language, and the gap

All 57 arXiv papers cited in the landscape review are in this folder, named by
arXiv number (for example `2411.06037.pdf`). Each was downloaded, checked to
be a readable PDF, and its title and abstract compared against the review.
**All 57 exist and match what the review says about them.**

These summaries are based on each paper's own title and abstract (in
`abstracts.txt`), not a full read of every paper. The eight papers closest to
our work are marked **KEY** and are the ones to read in full.

---

## Group A. Can the model tell, before answering, whether it knows?

| Paper | What it does, simply |
|---|---|
| `2211.08411` Kandpal et al., *LLMs Struggle to Learn Long-Tail Knowledge* | A model answers a fact correctly roughly in proportion to how many training documents mentioned it. Rare facts are not learned. |
| `2406.12673` Gottesman & Geva, *KEEN* | Looks inside the model at how it represents a name (say "Napoleon") and predicts how well it will answer questions about it, before it writes anything. |
| `2506.09669` Chen et al., *Query-Level Uncertainty* **KEY** | One pass through the model, no answer generated, gives a score for "can I answer this?". Needs no training. |
| `2509.10625` *No Answer Needed* | Reads the model's internal state right after the question and predicts whether the coming answer will be right. Beats asking the model how confident it is. |
| `2412.12472` Li et al., *Knowledge Boundary survey* | A map of the field. Sorts knowledge into: known whatever the prompt; known only with the right prompt; unknown to this model; unknown to anyone. |
| `2607.07380` Dey & Ounis, *Interpretable Uncertainty* **KEY** | From one pass, separates "I lack the knowledge" (go and retrieve) from "the knowledge conflicts" (think harder). |

**What this group covers:** the model's own memory (source P) only. None of
them predicts whether the *web* or a *knowledge base* holds the answer.

## Group B. Confidently wrong: why agreement is not correctness

| Paper | What it does, simply |
|---|---|
| `2502.12964` Simhi et al., *CHOKE* | Shows models that know an answer can, after a trivial rewording, give a wrong one with high certainty. Uncertainty-based detectors miss these. |
| `2605.00939` *Stubborn Hallucinations* | Names errors the model repeats confidently and consistently. Asking many times and checking agreement cannot catch them. |
| `2508.14496` *Semantic Energy* | A new confidence score built from the model's raw outputs, aimed at the case where every sample agrees on a wrong answer. |
| `2406.15927` Kossen et al., *Semantic Entropy Probes* | Semantic entropy (ask several times, measure spread of meanings) is expensive; this predicts it from one pass. |
| `2608.00422` *TrAC* | After the model reasons to an answer, asks it again from its own reasoning and checks the answer holds. |
| `2406.02543` Abbasi-Yadkori et al., *To Believe or Not to Believe* | A mathematical measure that separates "the model does not know" from "the question has several right answers". |
| `2511.04418` *The Illusion of Certainty* | Proves the usual uncertainty scores only work when questions have one answer; on ambiguous questions they fall to chance. |
| `2505.22655` Kirchhof et al., position paper | Argues the standard two-way split of uncertainty breaks down for agents that can ask the user follow-up questions. |

**What this group covers:** evidence that the problem is real. They describe
the symptom; none explains it as "the answer was never in the source".

## Group C. Retrieval and multiple sources (closest to W and K)

| Paper | What it does, simply |
|---|---|
| `2411.06037` Joren et al., *Sufficient Context* **KEY** | Asks of the retrieved text: is this enough to answer? Finds big models answer wrongly rather than abstain when it is not. |
| `2410.22954` Hwang et al., *RA-RAG* **KEY** | Scores each source's trustworthiness by cross-checking sources against each other, then weights answers by that score. |
| `2410.07176` Wang et al., *Astute RAG* | Combines what the model knows with what was retrieved, checking each against the other to survive bad retrieval. |
| `2504.13079` Wang et al., *MADAM-RAG* | One agent per document; they debate over rounds and an aggregator settles conflicts. Also a dataset of conflicting evidence. |
| `2604.20854` Shin et al., *ERA* **KEY** | Represents "what the model knows" and "what was retrieved" as two separate bodies of evidence, measures their conflict, and abstains when it is high. |
| `2607.10491` *EvidentialRAG* **KEY** | Turns each retrieved chunk into evidence, keeps disagreement visible instead of averaging it away, then answers, answers with a warning, or abstains. **Tested on CRAG.** |
| `2603.05909` *InfoGatherer* | When a question is underspecified, decides whether to retrieve more or ask the user, and when to stop. |
| `2501.12835` Moskvoretskii et al., *Adaptive Retrieval* **KEY** | Compares 35 ways of deciding "should I retrieve?" and finds simple uncertainty scores do about as well as elaborate systems. |

**What this group covers:** each measures one thing. Sufficient Context:
whether the answer is there. RA-RAG: whether the source is trustworthy. ERA
and EvidentialRAG: whether sources conflict. None keeps "is it there" and "can
we get it" as two separate numbers per source, and none treats a curated
knowledge base differently from the web.

## Group D. Abstaining: when to say "I don't know"

| Paper | What it does, simply |
|---|---|
| `2506.09038` *AbstentionBench* | 20 datasets of questions that should not be answered. Bigger models do not abstain better; reasoning-tuned models abstain worse. |
| `2509.04664` Kalai et al., *Why Language Models Hallucinate* | Models guess because tests reward guessing. Proposes scoring that penalises wrong answers more than "I don't know". |
| `2512.14801` *Incentives or Ontology?* | A rebuttal: better scoring alone cannot fix it, because the model has no access to truth without an outside check. |
| `2601.20126` *Rewarding Intellectual Humility* | Trains models with a reward for abstaining; a moderate reward cuts wrong answers without much lost accuracy. |
| `2604.03904` *I-CALM* | Does the same through the prompt only: tell the model the payoffs for answering versus abstaining. |
| `2405.01563` *Conformal Abstention* | A statistical procedure that decides when to abstain, with a guaranteed limit on the error rate. |
| `2405.20947` *OR-Bench* | A benchmark for the opposite fault: models refusing questions they should answer. |
| `2609.00760` *Knowledge- and Safety-Based Refusals* | Finds "I don't know" refusals and "I won't" refusals share internal machinery but can be told apart. |
| `2607.10059` *AgentAbstain* | Tests whether tool-using agents know when not to *act*, with paired do / don't tasks. |

## Group E. Statistical guarantees (conformal prediction)

| Paper | What it does, simply |
|---|---|
| `2305.12616` Gibbs, Cherian & Candès | The theory: how to make a guarantee hold within chosen subgroups, not just on average. |
| `2406.09714` Cherian, Gibbs & Candès | Applies that to LLM output: filter out claims until what remains is correct with a stated probability, per topic. |
| `2402.10978` Mohri & Hashimoto | The original idea: make an answer vaguer until it is guaranteed correct. |
| `2506.20978` *Conformal-RAG* | The same guarantee for retrieval systems, holding within sub-domains. |
| `2602.01285` *MACI* | Uses several models together for better scores under the same guarantee. |
| `2604.13991` *Adaptive Conformal* | Shows one global threshold holds on average but fails within categories; adapts per prompt. |
| `2609.04445` *Conformity Breaks Conformal Prediction* | A warning: guarantees break when the model sees other agents confidently asserting a wrong answer. |

## Group F. Multi-step agents

| Paper | What it does, simply |
|---|---|
| `2412.01033` *SAUP* | Carries uncertainty forward through each step of an agent's work instead of scoring only the last step. |
| `2506.17419` *UProp* | Splits a step's uncertainty into its own part and the part inherited from earlier steps. |
| `2601.15703` Zhang et al., *Agentic UQ* | Early errors become "facts" for later steps. Stores confidence in memory and triggers reflection only when needed. |
| `2602.05073` Oh et al., survey | The reference survey for agent uncertainty; lists "uncertainty of different kinds of sources" as an open problem. |
| `2609.07395` Lin et al., taxonomy | Classifies where uncertainty arises in agents and argues a single final score is too coarse. |
| `2602.06948` *Agentic Overconfidence* | Agents that succeed 22% of the time predict 77%. Predicting before execution is no worse than after. |
| `2605.24756` *Proper Scoring Rules* | How to grade an agent's step-by-step confidence honestly. |
| `2509.21199` *Fano-Style Bound* | A theoretical ceiling: accuracy collapses once a multi-step question exceeds what one pass can hold. |
| `2607.10562` *CRiT-QA* | A multi-step benchmark with invented facts and decoy reasoning paths; accuracy falls as steps increase. |
| `2607.17535` *Salience Induction* | Shows a chain of true facts can still lead an agent to a wrong answer through what is made prominent. |

## Group G. Memory (source M)

| Paper | What it does, simply |
|---|---|
| `2606.24428` *Execute–Distill–Verify* | Agents that reflect on failures can store a wrong lesson and reuse it: the "self-confirmation trap". |
| `2607.22962` *ConsistencyGate* | Checks a fact several times before allowing it into memory. |
| `2610.27406` *More Memory, Worse Agents* | Stored rules reproduce their own errors; keeps raw experience and rebuilds guidance on demand. |
| `2611.14320` *WikiTrace* | Links each stored lesson to the original evidence so the agent can check it. |

## Group H. Measuring properly

| Paper | What it does, simply |
|---|---|
| `2411.00640` Miller, *Adding Error Bars to Evals* | How to report model test results with proper error bars. |
| `2503.01747` *Don't Use the CLT* | With fewer than a few hundred test items, the usual error bars are too small. Use other methods. |
| `2504.19254` and `2507.06196` *UQLM* | A paper and a Python package bundling many confidence-scoring methods. |
| `2511.01409` *LiveSearchBench* | A benchmark rebuilt from recent facts, so models cannot answer from memory; newer facts are harder. |

---

# The gap

Put the groups side by side and four things are missing.

**1. Nobody keeps "is the answer in this source?" separate from "can the agent
get it out?".**
Sufficient Context measures the first. RA-RAG measures something like the
second. ERA and EvidentialRAG fold both into one evidence score. Our g and r
are the first attempt to carry both, per source, all the way through.

**2. Predicting before the agent runs exists only for the model's own
memory.**
Group A does it for P. Nobody predicts, from the question, whether the *web*
or a *knowledge base* holds the answer. That is hypothesis H2 for W and K,
and it is ours to test.

**3. Nobody treats a curated knowledge base as a different kind of source from
the web.**
RA-RAG handles many sources but treats them as interchangeable. The W versus
K contrast is not in any of the 57.

**4. Nobody has shown the two quantities move independently.**
This is the gap our own results speak to. On real CRAG data, improving the
agent's search raised "found when present" from 0.070 to 0.267 while "not
present" stayed near 0.31. No paper here reports that kind of test.

## Where the gap is narrower than it looks

- **EvidentialRAG already reports on CRAG** and already routes to answer,
  warn or abstain. Any CRAG result we publish will be compared with it.
- **Dey & Ounis (`2607.07380`)** already separate "knowledge missing" from
  "knowledge conflicting" before answering, though only for the model's own
  memory.
- **Sufficient Context** already labels "the answer is not in the retrieved
  text", and does it with a model that reads the text, which is better than
  our word matching.

## What that means for the subgroup

The defensible claim is narrow and specific: **per-source coverage and
reliability, kept separate, predicted before execution, for the web and a
knowledge base, with evidence that the two move independently.** Lead with
that, use Sufficient Context as the membership method, and compare against
EvidentialRAG on CRAG.

## Reading order

1. `2411.06037` Sufficient Context
2. `2607.10491` EvidentialRAG
3. `2410.22954` RA-RAG
4. `2604.20854` ERA
5. `2506.09669` Query-Level Uncertainty
6. `2607.07380` Dey & Ounis
7. `2501.12835` Adaptive Retrieval
8. `2412.12472` Knowledge Boundary survey (for the vocabulary)
