// Dark, typography-led workshop deck with an explicit narrative arc.
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("./apply_theme.js");

const FIG = "/Users/shainmukungu/Desktop/knowing_where_not_to_look/results/figures/";

const DEEP = "142A47";
const INKD = "0E1F38";
const WHITE = "FFFFFF";
const BRIGHT = "EAF1FA";
const BODY = "AFC2DE";
const MUTED = "7E97BC";
const RULE = "33517A";
const REDL = "E08A91";
const NAVY = "1C4A80";

const THEME = {
  name: "Knowing Where Not to Look",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1A1A1C", lt1: WHITE, dk2: DEEP, lt2: "F2F2F2",
    accent1: NAVY, accent2: "B2303A", accent3: MUTED, accent4: "84B59F",
    accent5: "50808E", accent6: "B85042", hlink: NAVY, folHlink: MUTED,
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Knowing Where Not to Look team";
pres.title = "Knowing Where Not to Look";

pres.defineSlideMaster({ title: "DARKTITLE", background: { color: INKD }, objects: [] });
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: DEEP },
  objects: [],
  slideNumber: { x: 9.15, y: 5.24, w: 0.45, fontSize: 9, color: MUTED, align: "right" },
});

function kicker(slide, text) {
  slide.addText(text, { x: 0.62, y: 0.3, w: 5.0, h: 0.28, fontSize: 10,
    color: MUTED, charSpacing: 3, align: "left", margin: 0, isTextBox: true });
}

function title(slide, text) {
  slide.addText(text, { x: 0.6, y: 0.62, w: 8.8, h: 0.6, fontSize: 27,
    bold: true, fontFace: "Cambria", color: WHITE, align: "left", margin: 0,
    isTextBox: true });
}

function runsOf(text, color) {
  const parts = String(text).split("~");
  return parts.map((seg, i) => ({
    text: seg,
    options: { subscript: i % 2 === 1, color },
  })).filter(r => r.text.length);
}

function eq(slide, lines, x, y, w, size) {
  slide.addText(
    lines.flatMap((t, i) => {
      const rr = runsOf(t, BRIGHT);
      rr[rr.length - 1].options.breakLine = i < lines.length - 1;
      return rr;
    }),
    { x, y, w, h: lines.length * (size / 72) * 1.8 + 0.12, fontSize: size,
      fontFace: "Cambria", color: BRIGHT, align: "left", valign: "top",
      margin: 0, isTextBox: true, lineSpacingMultiple: 1.65 });
}

function support(slide, text, y, opts) {
  slide.addText(text, { x: 0.62, y, w: 8.3, h: (opts && opts.h) || 0.5,
    fontSize: 13, color: (opts && opts.color) || MUTED, align: "left",
    margin: 0, isTextBox: true });
}

function plate(slide, file, aspect, w, cx, yTop) {
  const h = w / aspect;
  const pad = 0.14;
  const x = cx - w / 2;
  slide.addShape(pres.ShapeType.rect, {
    x: x - pad, y: yTop, w: w + 2 * pad, h: h + 2 * pad,
    fill: { color: WHITE }, line: { type: "none" },
  });
  slide.addImage({ path: FIG + file, x, y: yTop + pad, w, h });
  return yTop + h + 2 * pad;
}

function ruleTable(slide, rows, opts) {
  const n = rows.length;
  const head = ri => (opts.noHeader ? false : ri === 0);
  const styled = rows.map((row, ri) => row.map((cell, ci) => ({
    text: /[~∈∉]/.test(String(cell))
      ? runsOf(cell, ri === 0 ? WHITE
               : ((opts.accentCol === ci && ri > 0) ? BRIGHT : BODY))
          .map(r => ({ ...r, options: { ...r.options, fontFace: "Cambria" } }))
      : cell,
    options: {
      bold: head(ri),
      color: head(ri) ? WHITE
        : ((opts.accentCol === ci) ? BRIGHT : BODY),
      fill: { color: DEEP },
      fontSize: opts.fontSize || 14,
      align: ci === 0 ? "left" : (opts.alignRest || "left"),
      valign: "middle",
      border: [
        { type: ri === 0 ? (opts.noHeader ? "solid" : "none") : "solid",
          color: ri === 0 ? MUTED : RULE, pt: ri === 0 ? 1 : 0.5 },
        { type: "none" },
        { type: head(ri) ? "solid" : (ri === n - 1 ? "solid" : "none"),
          color: head(ri) ? MUTED : RULE, pt: head(ri) ? 1 : 0.5 },
        { type: "none" },
      ],
    },
  })));
  slide.addTable(styled, { x: opts.x, y: opts.y, w: opts.w, colW: opts.colW,
    margin: 0.07, rowH: opts.rowH || 0.36 });
}

function lead(slide, pairs, y, size, gap) {
  slide.addText(
    pairs.flatMap(([t, strong], i) => {
      const r = { text: t, options: { color: strong ? BRIGHT : BODY,
                                      bold: !!strong,
                                      breakLine: i < pairs.length - 1 } };
      return [r];
    }),
    { x: 0.62, y, w: 8.8, h: pairs.length * ((size || 16) / 72) * 2.1 + 0.25,
      fontSize: size || 16, align: "left", margin: 0, isTextBox: true,
      lineSpacingMultiple: 1.45, paraSpaceAfter: gap || 10 });
}

// 1 · Title
{
  const s = pres.addSlide({ masterName: "DARKTITLE" });
  s.addText("Knowing Where\nNot to Look", {
    x: 0.9, y: 1.3, w: 8.4, h: 1.95, fontSize: 54, bold: true,
    fontFace: "Cambria", color: WHITE, align: "left", margin: 0,
    isTextBox: true, lineSpacingMultiple: 1.04 });
  s.addText("Query- and source-resolved confidence for agents", {
    x: 0.92, y: 3.45, w: 8.4, h: 0.5, fontSize: 18, color: BODY,
    align: "left", margin: 0, isTextBox: true });
  s.addText("AI, Uncertainty and Simulation   ·   Mauritius   ·   20 November 2026", {
    x: 0.92, y: 4.75, w: 8.4, h: 0.35, fontSize: 12, color: MUTED,
    align: "left", margin: 0, isTextBox: true });
  s.addNotes("The project asks whether an agent can know, before it runs, where to look, where not to look, and when no source will do. The talk walks the full arc: the problem, the gap in existing methods, the idea, how it was tested, six measured results, and the limits. The code is public and appears on the last slide.");
}

// 2 · The problem
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "P R O B L E M");
  title(s, "Agents answer when they should not");
  lead(s, [
    ["An agent asked for what its sources do not contain still answers.", true],
    ["Cause one: the answer is in the corpus and retrieval misses it.", false],
    ["Cause two: the answer is written nowhere the agent can reach.", false],
  ], 1.62, 17, 14);
  support(s, "The two causes demand opposite repairs, and a single confidence number cannot say which one is happening.", 3.75, { h: 0.8 });
  s.addNotes("The concrete problem first. On CRAG, the benchmark used throughout, straightforward retrieval-augmented generation reaches about forty-four percent accuracy with about thirty percent hallucination: the system answers confidently where it should not. When it is wrong there are two different causes. Either the answer is present and retrieval took the wrong route, which better retrieval fixes, or the answer is written nowhere the system can reach, where searching harder only returns the nearest wrong answer more confidently. The repairs are opposite: fix the pipeline, or stop searching this source. Any confidence that arrives as a single number cannot tell the operator which repair is indicated. That is the problem.");
}

// 3 · The gap
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "G A P");
  title(s, "What existing methods miss");
  eq(s, [
    "ĉ_agree(y)  =  (1/N) Σᵢ 1{ y(τᵢ) = y }        →        Q(y | q),  not  Pr(y = y*)",
  ], 0.62, 1.55, 8.8, 17);
  lead(s, [
    ["Sampling methods estimate the agent's own distribution, not correctness.", false],
    ["Corpus coverage and retrieval skill are merged into one score; the diagnosis is unrecoverable.", false],
    ["Nothing predicts, before execution, whether an external corpus can contain the answer.", false],
  ], 2.6, 15, 12);
  support(s, "57 papers reviewed; none separates the two quantities, and none tests their independence.", 4.42, { h: 0.7 });
  s.addNotes("Why existing methods do not solve it. Self-consistency and semantic entropy run the agent several times and read agreement as confidence; as N grows that estimate converges to the agent's own sampling distribution, which equals correctness only when the proposal matches the target. On a question whose answer is written nowhere, every run re-reads the same absence and agrees perfectly. Beyond sampling, the evidence-scoring line of work merges corpus coverage and retrieval skill into one number, after which the diagnosis cannot be recovered. And pre-execution prediction exists only for what the model itself knows, never for whether an external corpus holds the answer. We reviewed all fifty-seven papers in the project's landscape survey: none separates the two quantities per source, and none tests whether they are independent.");
}

// 4 · Outline
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "T H I S   T A L K");
  title(s, "The route from here");
  ruleTable(s, [
    ["idea", "two numbers per source, kept apart: ghost mass and reliability"],
    ["test", "a double dissociation on 4,409 questions; nine estimators under proper scoring rules"],
    ["results", "six, each with intervals and a baseline"],
    ["limits", "negative results stated as results, then what the project hands on"],
  ], { x: 0.62, y: 1.75, w: 8.8, colW: [1.6, 7.2], fontSize: 14.5,
       accentCol: 0, rowH: 0.56, noHeader: true });
  s.addNotes("The route through the talk. First the idea: resolve confidence by source, into a ghost mass, the probability the corpus cannot contain the answer, and a reliability, the probability the agent finds it when it is there. Second the test: these two numbers are only worth keeping apart if they are genuinely different properties, so the central experiment is a double dissociation, backed by nine standard uncertainty estimators measured under proper scoring rules so the comparison is fair. Then six results, each with confidence intervals and a baseline or permutation control. Then the limits, including the negative results, and what the project hands to the next stage.");
}

// 5 · Idea: formalism
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "I D E A");
  title(s, "Two numbers per source, kept apart");
  eq(s, [
    "g~s~(q)  =  Pr( y* ∉ C~s~ | φ(q) )",
    "r~s~(q)  =  Pr( ŷ~s~ = y* | y* ∈ C~s~ , φ(q) )",
  ], 0.62, 1.55, 5.6, 19);
  s.addText([
    { text: "ghost mass", options: { breakLine: true } },
    { text: "reliability", options: {} },
  ], { x: 6.5, y: 1.55, w: 2.4, h: 1.35, fontSize: 14, color: MUTED,
       align: "left", margin: 0, isTextBox: true, lineSpacingMultiple: 2.28 });
  ruleTable(s, [
    ["class", "condition", "indicated action"],
    ["covered", "y* ∈ C~s~ , reached", "answer"],
    ["rare passage", "y* ∈ C~s~ , missed", "repair retrieval"],
    ["ghost", "y* ∉ C~s~", "change source or abstain"],
  ], { x: 0.62, y: 3.05, w: 8.8, colW: [2.0, 3.2, 3.6], fontSize: 14, accentCol: 2 });
  s.addNotes("The idea in two definitions. Each source, the model's parameters, the web, the knowledge base, memory, has a corpus. Ghost mass is the probability the true answer is not in that corpus at all. Reliability is conditional: the chance the agent finds the answer given that it is there, skill on winnable questions rather than accuracy. Phi of q is computed from the question and the retrieval only, before any answer exists. The three classes follow, and each indicates a different action: answer, repair retrieval, or change source and abstain. Keeping the numbers apart is what makes the action decidable; merged, it is not.");
}

// 6 · Idea: decomposition
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "I D E A");
  title(s, "Where sampling cannot reach");
  eq(s, ["U~s~(q)   =   U_alea(q)   +   U_param(q | s)   +   g~s~(q)"],
     0.62, 1.7, 8.8, 21);
  ruleTable(s, [
    ["term", "meaning", "reduced by"],
    ["U_alea", "the question is ambiguous", "asking the user"],
    ["U_param", "held, but the agent is unsure", "sampling, retrieval"],
    ["g~s~", "cannot be held", "changing source only"],
  ], { x: 0.62, y: 2.8, w: 8.8, colW: [1.7, 3.9, 3.2], fontSize: 14, accentCol: 2 });
  s.addNotes("Why this is an uncertainty story. The usual split is aleatoric against epistemic. Ghost mass is a third term: epistemic about the corpus rather than about the model. More samples are drawn from a corpus that does not contain the answer, so no amount of sampling moves it; only consulting a different source does. The additive form is a reporting convention rather than a theorem, following Kirchhof and colleagues, with the ghost term estimated operationally from labelled coverage. It is the term standard estimators cannot see, and the reason a separate per-source estimate earns its keep.");
}

// 7 · Test design
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "T E S T   D E S I G N");
  title(s, "If the split is real, it must dissociate");
  s.addText([
    { text: "Objection:  ", options: { bold: true, color: REDL } },
    { text: "these are one quantity, split arbitrarily. Every ghost is retrieval failing harder.",
      options: { color: BRIGHT } },
  ], { x: 0.62, y: 1.58, w: 8.8, h: 0.8, fontSize: 15.5, align: "left",
       margin: 0, isTextBox: true });
  ruleTable(s, [
    ["manipulation", "prediction"],
    ["improve the agent, corpus fixed", "r rises, g unchanged"],
    ["grow the corpus, agent fixed", "g falls, r unchanged"],
  ], { x: 0.62, y: 2.5, w: 8.8, colW: [4.6, 4.2], fontSize: 15, accentCol: 1, rowH: 0.44 });
  support(s, "CRAG · 4,409 questions · 738 paired at five and fifty pages · agent byte-identical across the corpus arm", 4.2, { h: 0.8 });
  s.addNotes("The design, framed against the strongest objection: that ghost mass and reliability are one messy quantity split arbitrarily. If reliability belongs to the agent, improving the agent with the corpus fixed should move r and leave g alone. If ghost mass belongs to the corpus, growing the corpus tenfold with the agent held byte-identical should move g and leave r alone. Both arms ran on CRAG: three retrieval generations for the first; for the second, the same seven hundred and thirty-eight questions at five and at fifty pages. Alongside, nine standard estimators from LM-Polygraph were measured with isotonic calibration on a held-out split, so every claim about existing methods is against their real numbers, not a caricature. None of the fifty-seven reviewed papers runs this design.");
}

// 8 · Result 1
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T   1");
  title(s, "Each knob moves exactly one quantity");
  plate(s, "plate_dissociation.png", 2.415, 7.9, 5.0, 1.42);
  support(s, "Δg = −0.168, 95% CI [−0.195, −0.142]   ·   membership flips: 124 gained, 0 lost", 5.0);
  s.addNotes("Result one, the dissociation. Left panel reliability, right panel ghost mass; grey is before, colour is after. Improving the agent four times over moved reliability from 0.066 to 0.286 and left ghost mass flat. Growing the corpus tenfold halved ghost mass, 0.322 to 0.154, interval nowhere near zero, and moved reliability by eight thousandths. Each manipulation moves exactly one quantity: r is a property of the agent, g of the corpus. The validity check: the five-page corpus is a subset of the fifty-page one, so a sound labeller can only gain members. We gained one hundred and twenty-four, lost zero.");
}

// 9 · Result 2
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T   2");
  title(s, "Ghost mass is depth-dependent");
  plate(s, "plate_depth.png", 2.041, 6.7, 5.0, 1.4);
  support(s, "realtime: g falls 0.481 → 0.123, the largest drop of any class", 5.02);
  s.addNotes("Result two, a surprise. Split by how fast each answer changes in the world. At five pages, realtime questions carry the heaviest ghost mass and the natural reading is staleness. At fifty pages the picture inverts: realtime drops to 0.123 and becomes the best-covered class, three times the drop of static questions. The fresh figures existed all along, lower in the ranking than a five-page window reaches. Apparent staleness was substantially retrieval depth, and which questions are ghosts depends on how deep the system reads. This refines the specification's working hypothesis: ghost mass grows with recency at shallow depth, and the relation inverts at depth.");
}

// 10 · Result 3
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T   3");
  title(s, "Absence is predictable before execution");
  ruleTable(s, [
    ["source", "AUROC", "permutation"],
    ["K, knowledge graph", "0.83", "0.49"],
    ["W, five pages", "0.51", "0.50"],
    ["W, fifty pages", "0.651", "0.484"],
  ], { x: 0.62, y: 1.62, w: 8.8, colW: [4.4, 2.2, 2.2], fontSize: 15,
       accentCol: 1, alignRest: "left", rowH: 0.44 });
  s.addText([
    { text: "The five-page null was an artifact: constant features.  ",
      options: { color: BODY } },
    { text: "Gate: false premise detected at 0.868 from text alone.",
      options: { color: BRIGHT } },
  ], { x: 0.62, y: 4.1, w: 8.8, h: 0.8, fontSize: 13.5, align: "left",
       margin: 0, isTextBox: true });
  s.addNotes("Result three: the core hypothesis, that cheap pre-execution features predict whether the corpus holds the answer. On the knowledge base it holds at 0.83 against a permutation baseline at chance. On the web at five pages it appeared refuted, 0.51; that null was a benchmark artifact, every question carrying exactly five unscored pages, so the informative features were constants. At fifty pages the features vary and the same probe reaches 0.651, above the project's bar of 0.6. Before any source matters there is also a gate: a plain text classifier detects false premises at 0.868 from the question alone, the omega component of phi.");
}

// 11 · Result 4
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T   4");
  title(s, "Abstention breaks the standard estimators");
  plate(s, "plate_inversion.png", 2.395, 7.5, 5.0, 1.42);
  support(s, "conditioning on abstention: MeanTokenEntropy 0.047 → 0.966, nothing harmed", 5.0);
  s.addNotes("Result four, about the baselines themselves. Red dots are raw AUROC, blue after conditioning on abstention. Headline numbers spread from 0.034 to 0.97 on the same arm, and the whole spread is about abstention: a declining model emits its refusal with near-zero token entropy, so entropy-family estimators read confident refusal as confident assertion and invert below chance. Sequence log-likelihood happens to encode refusal as uncertain, so it looks strong. Make the encoding explicit, abstention as maximal uncertainty, and the inverted estimator repairs from 0.047 to 0.966 with nothing harmed. Among answered questions every estimator sits between 0.59 and 0.67; the spread was never about discrimination. The repair is one line and portable to any abstaining system.");
}

// 12 · Result 5
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T   5");
  title(s, "The average hides the structure");
  plate(s, "plate_reliability.png", 5.087, 8.76, 5.0, 1.45);
  ruleTable(s, [
    ["expected calibration error", "value"],
    ["overall", "0.030   [0.016, 0.073]"],
    ["per KAP cell", "0.045 to 0.130"],
  ], { x: 0.62, y: 3.6, w: 8.8, colW: [4.4, 4.4], fontSize: 14, rowH: 0.4, accentCol: 1 });
  s.addNotes("Result five, calibration. Measured overall, expected calibration error is 0.030 and looks excellent. Measured inside each cell, every cell is worse, 0.045 to 0.130: overconfident where answers move, underconfident where they sit still, cancelling to a marginal number that is accurate and uninformative. The same structure shows on the recency axis as a confidence-accuracy gap of 0.248 on realtime against 0.097 on static, non-overlapping intervals. Marginal conformal coverage, for completeness, held in every cell, but conservatively, with coverage near one; the structure lives in calibration error, not coverage.");
}

// 13 · Result 6
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T   6");
  title(s, "Where the ignorance mass sits");
  eq(s, [
    "product rule answers only if     r~s~  >  g~s~ / (1 − g~s~)",
    "Dempster-Shafer:     m({ŷ~s~}) = r~s~ ,      m(Θ) = 1 − r~s~",
  ], 0.62, 1.62, 8.8, 19);
  s.addText([
    { text: "K would need r > 2.7.   ", options: { color: REDL, bold: true } },
    { text: "Ignorance on Θ instead: ECE 0.102 against 0.163.",
      options: { color: BRIGHT } },
  ], { x: 0.62, y: 3.12, w: 8.8, h: 0.8, fontSize: 16.5, align: "left",
       margin: 0, isTextBox: true });
  s.addNotes("Result six, found by carrying the two numbers to the decision rule. The Bayesian product form the project started from spreads each source's ghost mass as noise over every candidate, including the one that source proposed. Solved for when it answers at all, the condition is r greater than g over one minus g; the knowledge base would need reliability above 2.7, impossible for a probability, and empirically it silenced a source answering correctly every time. Dempster-Shafer differs in one respect: unreliability is parked on the whole frame as uncommitted belief. Measured on real evidence it is the better calibrated rule. The two conflict measures, kappa and the Bayesian evidence ratio from the cosmology tension literature, tied on the seventy real disagreements held so far.");
}

// 14 · Limits
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "L I M I T S");
  title(s, "Negative results, stated as results");
  s.addText([
    { text: "H4 refuted: marginal conformal met 90% coverage in every cell.", options: { bullet: { code: "2022", indent: 16 }, breakLine: true } },
    { text: "Memory source: g = 0.995 on unique queries.", options: { bullet: { code: "2022", indent: 16 }, breakLine: true } },
    { text: "A third class, derivable but never stated, is miscounted as ghost.", options: { bullet: { code: "2022", indent: 16 }, breakLine: true } },
    { text: "Readers are small local models. Every reader figure is a floor.", options: { bullet: { code: "2022", indent: 16 } } },
  ], { x: 0.62, y: 1.7, w: 8.8, h: 2.9, fontSize: 16.5, color: BRIGHT,
       align: "left", margin: 0, isTextBox: true, paraSpaceAfter: 18 });
  s.addNotes("The limits, stated as results. Per-cell conformal added nothing because marginal coverage already held everywhere, though the test was conservative. The memory source had nothing to recall on a benchmark of unique questions; measuring it needs repeated or related queries. Forty-four percent of sports questions ask for aggregates over records the graph physically holds: derivable but never stated, which the membership test records as ghost, inflating it with what is really a capability gap. All reader results come from small local models, so every reader number is a floor. And one honest weakening of the project's own premise: sampling is not blind to absence, it carries weak signal near 0.64, mostly through the abstention rate.");
}

// 15 · Close
{
  const s = pres.addSlide({ masterName: "DARKTITLE" });
  s.addText(runsOf("( r~s~(q) ,  g~s~(q) )", WHITE), {
    x: 0.9, y: 1.75, w: 8.2, h: 1.0, fontSize: 44, bold: true,
    fontFace: "Cambria", color: WHITE, align: "left", margin: 0, isTextBox: true });
  s.addText("per question, per source · predicted before execution · carried unmerged to the decision rule", {
    x: 0.92, y: 2.9, w: 8.2, h: 0.68, fontSize: 15, color: BODY,
    align: "left", margin: 0, isTextBox: true });
  s.addText("dissociation shown in both directions · absence predictable at 0.65 to 0.83 · estimator repair 0.047 → 0.966", {
    x: 0.92, y: 3.72, w: 8.2, h: 0.7, fontSize: 13, color: MUTED,
    align: "left", margin: 0, isTextBox: true });
  s.addText("github.com/shecode-hue/knowing-where-not-to-look", {
    x: 0.92, y: 4.75, w: 8.2, h: 0.4, fontSize: 13, color: MUTED,
    align: "left", margin: 0, isTextBox: true });
  s.addNotes("The take-home is an interface, not a tool: for each question and each source, a predicted reliability and a predicted ghost mass, computed before execution and carried unmerged into whatever fusion rule the decision stage prefers. Behind it: the dissociation shown in both directions with intervals and a passed monotonicity check, absence predictable before execution on both sources, and a one-line repair for abstention-inverted estimators. Open items: a frontier reader for scaling, the remaining fifty-page pairs, and more web-against-knowledge-base disagreements for the conflict question. Code and every result table are in the repository.");
}

(async () => {
  await pres.writeFile({ fileName: "knowing_where_not_to_look.pptx" });
  await applyTheme("knowing_where_not_to_look.pptx", THEME);
  console.log("deck written");
})();
