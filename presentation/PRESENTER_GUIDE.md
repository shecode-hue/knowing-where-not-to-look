# Presenter guide, slide by slide

Plain-language notes for the thirteen slides of *Knowing Where Not to Look*.
Each section explains what is on the slide, what it means, and what to say.
The wording is written to be spoken.

---

# Slide 1. Title

**On the slide:** the project name over a photograph of the Very Large
Telescope platform at night, with the subtitle "Query- and source-resolved
confidence for agents" and the workshop line.

**What it means:** the title is the whole idea. An agent that knows where
*not* to look wastes no effort searching sources that cannot help it, and
does not convince itself with answers from places that never held the truth.
"Query- and source-resolved" means the confidence is computed for each
question and for each source separately, never as one blended number.

**What to say:** this project asks whether a system can know three things
before it runs: where to look, where not to look, and when no source will
do. Everything in the talk is measured on real benchmark data. The code is
public, and the link is on the last slide.

---

# Slide 2. Agents answer when they should not

**On the slide:** three plain statements over a photograph of library
stacks, and a line of benchmark numbers at the bottom.

**What it means:** this is the problem. When a system is asked for
something its sources do not contain, it still produces an answer. There
are only two ways to be wrong. Either the answer exists in the material and
the search missed it, or the answer is written nowhere the system can
reach. These two failures look identical from the outside, and they demand
opposite responses. If the answer was there and missed, the fix is a better
search. If the answer was never there, searching harder only returns the
nearest wrong thing with more confidence, so the right move is to stop,
switch source, or admit ignorance. A single confidence number cannot tell
the two apart, so the system cannot know which repair to make.

**What to say:** quote the benchmark line on the slide. On CRAG, the
4,409-question benchmark used throughout this work, ordinary
retrieval-augmented generation reaches about 44 percent accuracy with about
30 percent hallucination. Nearly a third of what such a system says is
confidently wrong, and today it cannot tell you why it was wrong, which
means it cannot fix itself.

---

# Slide 3. The route from here

**On the slide:** four rows. Idea, test, results, limits.

**What it means:** this is the map of the talk, so the audience always
knows where they are. The idea is to keep two numbers per source instead of
one blended confidence. The test is an experiment designed to prove the two
numbers are genuinely different things. The results are six, each with its
sample size and a control. The limits section reports what failed, openly.

**What to say:** walk the four rows in one breath each. The idea: every
source gets two numbers, a ghost mass, which is the chance it cannot
contain the answer, and a reliability, which is the chance the system finds
the answer when it is there. The test: an experiment where one thing is
changed at a time, on 4,409 real questions. The results: six findings, and
every number on every slide carries the size of the sample it came from.
The limits: the things that did not work, stated as plainly as the things
that did.

---

# Slide 4. Two numbers per source, kept apart

**On the slide:** two definitions in mathematical form, labelled in plain
words at the side, and a three-row table of classes.

**What it means:** this is the only theory slide, and it carries the whole
idea. Each source, whether it is the model's own memory of training, the
open web, or a curated knowledge base, has a corpus, which is simply
everything that source could ever say. Ghost mass, written g, is the
probability that the true answer is not in that corpus at all. Reliability,
written r, is the probability that the system finds the answer given that
it is in there. The phrase "given that" matters: r is skill on winnable
questions only, so it never gets blamed for questions that were impossible.
The table below turns the two numbers into actions. If the answer is
present and found, answer. If present and missed, fix the retrieval. If
absent, change source or abstain. Keeping g and r separate is exactly what
makes the right action computable.

**What to say:** both numbers are predicted from the question and the
retrieval alone, before any answer is generated. Nothing downstream of an
answer is allowed to leak in. Then make the one-number point: merge g and r
into a single confidence and you can still rank answers, but you can no
longer decide what to do when confidence is low, because you cannot tell a
search failure from a coverage failure.

---

# Slide 5. The six results

**On the slide:** six numbered lines, each a finding with its headline
number.

**What it means:** the full payload of the talk in one view, before the
detail. Each line is one of the next six slides compressed to a sentence.

**What to say:** read all six lines, slowly, numbering them aloud. One:
growing the corpus tenfold halves ghost mass while reliability does not
move, which proves the two numbers measure different things. Two: the ghost
mass of fast-changing questions was mostly retrieval depth, not staleness.
Three: whether a source holds the answer can be guessed before running, at
useful accuracy, on three of the four sources. Four: standard uncertainty
estimators misread a refusal as confidence, and a one-line fix repairs
them. Five: calibration that looks excellent on average is hiding large
errors inside question groups. Six: the fusion rule the project started
from can never answer, and the classical alternative is better calibrated.
Tell the audience each gets one slide with samples and controls.

---

# Slide 6. Corpus times ten: g falls 0.168, r moves 0.008

**On the slide:** a two-panel figure. Left panel, reliability under two
manipulations. Right panel, ghost mass under the same two. Grey bars are
before, coloured bars after. Below, a definition line and the confidence
interval.

**What it means:** this is the central experiment, a double dissociation.
The objection it answers is that ghost mass and reliability might be one
quantity split arbitrarily, every ghost being just a search that failed
harder. The test changes one thing at a time. First the retriever was
upgraded, from simple keyword overlap to a modern three-stage search, while
the corpus stayed fixed at five pages per question. Reliability jumped from
0.066 to 0.286 and ghost mass did not move. Then the corpus was grown from
five pages to fifty on the same 738 questions, with the retriever
byte-identical. Ghost mass halved, 0.322 to 0.154, and reliability moved by
eight thousandths. Each knob moved exactly one number.

**What to say:** point at the panels in order. Explain the built-in honesty
check: because the five-page corpus is contained in the fifty-page corpus,
a correct labeller can only ever gain members, never lose them. We gained
124 and lost zero. A single loss would have exposed noise in our own
measurement. Close with the claim: r belongs to the agent, g belongs to the
corpus, and no paper in the fifty-seven we reviewed runs this test.

---

# Slide 7. Realtime ghost mass: 0.481 to 0.123 at depth

**On the slide:** a bar chart of ghost mass by how fast the answer changes
in the world, static to realtime, at five pages and at fifty, with the
sample size under each class.

**What it means:** a surprise we did not predict. At five pages, questions
whose answers change by the second, stock prices, sports scores, carried
the heaviest ghost mass, 0.481, and the natural reading was staleness: the
web is out of date for fast-moving facts. At fifty pages that explanation
collapses. Realtime drops to 0.123 and becomes the best-covered class of
all. The fresh numbers existed all along, just further down the search
ranking than a five-page window could reach.

**What to say:** apparent staleness was substantially a depth problem, not
a time problem. Which questions look impossible depends on how deep the
system reads. This refines the project's own working hypothesis, which
expected ghost mass to grow with recency: that is true at shallow depth and
inverts at depth. It is also a practical lesson: before concluding a source
cannot know something, check how much of the source you are actually
reading.

---

# Slide 8. Coverage guessable in advance: AUROC 0.65 to 0.83

**On the slide:** a method line, then a table with one row per source:
the features the prediction uses, the score, a shuffled control, and the
held-out sample size. Below, one line for memory and one for the gate.

**What it means:** the claim is that you can estimate whether a source
holds the answer before generating anything. The method is deliberately
simple, a logistic probe, which is a small classifier fitted on one set of
questions and scored on a different set it never saw. The score, AUROC,
has a plain meaning: take one question whose answer is in the source and
one whose answer is not, and AUROC is the chance the probe ranks them the
right way round. A coin flip scores 0.5. Every row carries a shuffled
control, which is the same probe scored against scrambled labels, to show
what pure luck looks like at that sample size.

**What to say:** go down the rows. For the model's own knowledge, the
probe reads nothing but the question text and reaches 0.69. For the
knowledge graph, features like whether the entity was found at all reach
0.83. For the web the story is the interesting one: at five pages the probe
scored 0.51, indistinguishable from luck, and we nearly reported that
openly as a refutation. It was an artifact. Every question carried exactly
five pages, so the informative features were constants. At fifty pages the
same probe reaches 0.651. Memory is the honest exception, with nothing to
predict. Finish with the gate: a classifier on the question text alone
detects false-premise questions at 0.868, so part of knowing where not to
look is decidable before consulting any source at all.

---

# Slide 9. Refusal reads as confidence: 0.047 to 0.966

**On the slide:** a dot plot. One row per standard uncertainty estimator,
a red dot for its raw score, a blue dot after the fix, the chance line
dashed at 0.5. The axis label carries the sample: 293 questions, ten
samples each.

**What it means:** the field's standard uncertainty estimators were
measured fairly, using the community library, with calibration fitted on
one split and scores reported on another. Several of them score below 0.5,
which is worse than guessing, and that means they are not noisy, they are
backwards. The mechanism is simple once seen. When a model declines to
answer it emits its refusal with near-total certainty token by token, so
entropy-based estimators read a confident refusal as a confident assertion.
The fix is one line: treat an abstention as maximal uncertainty explicitly,
instead of letting the estimator infer it from token statistics. The worst
estimator repairs from 0.047 to 0.966, and nothing is harmed.

**What to say:** this matters beyond our project. Any system that is
allowed to refuse, which is any honest system, will poison these estimators
in exactly this way. Also say what the repair does not do: among questions
the model actually answers, every estimator sits between 0.59 and 0.67, so
none of them is a strong judge of correctness. The spectacular spread in
headline scores was never about discrimination, only about how each
estimator happens to encode a refusal.

---

# Slide 10. Calibration: 0.030 on average hides 0.130 in the cells

**On the slide:** a strip of five reliability diagrams, one per question
group, and a two-row table of calibration error.

**What it means:** a confidence is calibrated when the number means what it
says, so of all the times the system says seventy percent, about seventy
percent are right. Expected calibration error, ECE, measures the gap
between stated confidence and actual accuracy, and lower is better.
Measured over all questions at once, our best estimator scores 0.030,
which looks excellent. Measured inside each question group separately,
groups defined by how fast the answer moves, how popular the entity is,
and how many reasoning steps are needed, every single group is worse than
the average, from 0.045 up to 0.130.

**What to say:** the errors cancel. The system is overconfident where
answers move quickly and underconfident where they sit still, and the two
mistakes average into a number that is accurate and useless. The same
pattern shows as a confidence-accuracy gap of 0.248 on realtime questions
against 0.097 on static ones, with intervals that do not overlap. The
lesson is to never trust a single marginal calibration number: report
calibration inside the groups you care about, because the average is
hiding exactly the region where the system fails.

---

# Slide 11. The product rule is mute; Dempster-Shafer calibrates better

**On the slide:** two short formal lines, the condition under which the
product rule can answer at all, and the Dempster-Shafer assignment. Below,
the key numbers.

**What it means:** this result fell out of carrying g and r all the way to
the decision. The fusion rule the project started from combines sources by
multiplying, and it spreads each source's ghost mass as noise over every
candidate answer, including the one the source itself proposed. Solve that
algebra for the condition under which answering ever beats staying silent
and it requires r to exceed g divided by one minus g. For our knowledge
base that means reliability above 2.7, and no probability exceeds one. We
confirmed it empirically: the rule silenced a source that was answering
correctly every single time it spoke. The classical alternative,
Dempster-Shafer, differs in one decision: the unreliable share of belief is
parked on "I do not know" rather than spread across answers. Measured on
real evidence, it is the better calibrated of the two, 0.102 against 0.163
on 195 held-out questions.

**What to say:** the defect went unnoticed in the literature because
nobody carries the two numbers separately into the decision rule, which is
precisely the gap this project fills. Mention the tie honestly: the two
measures of conflict between sources scored the same on the seventy real
disagreements we hold, so that question stays open and needs more data.

---

# Slide 12. Negative results, stated as results

**On the slide:** four bullet lines.

**What it means:** four things did not work, and saying so is part of the
work. First, the per-group coverage guarantee added nothing here, because
the plain version already met its target in every group, though the test
was conservative. Second, the memory source had nothing to recall, since
the benchmark never repeats a question; its ghost mass is 0.995, and
measuring memory properly needs repeated or related queries. Third, a
whole class of questions is being miscounted: in sports and finance, 44
percent of questions ask for totals or averages over records the source
physically holds, so the answer is derivable but written nowhere, and our
membership test calls that a ghost when it is really a computation gap.
Fourth, every reader result in this talk comes from small local models, so
every reader number is a floor, not a ceiling.

**What to say:** deliver these at the same pace and in the same tone as
the successes. Add the one honest weakening of our own premise: sampling
is not completely blind to absence, it carries weak signal, around 0.64,
mostly through how often the model refuses. Our claim is the narrower one:
the signal is too weak to rely on, which is why the separate estimate of
ghost mass earns its place.

---

# Slide 13. Close: the pair (r, g)

**On the slide:** the pair of symbols large over the laser guide star
photograph, one line saying what they are, one line of the three headline
numbers, and the repository address.

**What it means:** the deliverable of the project is not a tool, it is an
interface. For every question and every source, two numbers, predicted
before execution, carried unmerged into whatever decision rule the next
stage prefers. Behind the pair stand the dissociation shown in both
directions, coverage predictable in advance on three sources, and the
estimator repair.

**What to say:** the photograph is a telescope firing a laser at the exact
point in the sky it needs, which is the thesis in one image. Close with
the open items, a stronger reader for the scaling question, the remaining
fifty-page data, more real disagreements between web and knowledge base,
and point to the repository, where the code, the data preparation and
every table in this talk can be reproduced.
