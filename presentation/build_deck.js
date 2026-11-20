// Dark, typography-led workshop deck: sparse slides, full prose in the notes.
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
  slide.addText(text, { x: 0.62, y: 0.3, w: 4.0, h: 0.28, fontSize: 10,
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
  slide.addText(text, { x: 0.62, y, w: 8.3, h: (opts && opts.h) || 0.5, fontSize: 13,
    color: (opts && opts.color) || MUTED, align: "left", margin: 0,
    isTextBox: true });
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
  const styled = rows.map((row, ri) => row.map((cell, ci) => ({
    text: /[~\u2208\u2209]/.test(String(cell))
      ? runsOf(cell, ri === 0 ? WHITE
               : ((opts.accentCol === ci && ri > 0) ? BRIGHT : BODY))
          .map(r => ({ ...r, options: { ...r.options, fontFace: "Cambria" } }))
      : cell,
    options: {
      bold: ri === 0,
      color: ri === 0 ? WHITE : ((opts.accentCol === ci && ri > 0) ? BRIGHT : BODY),
      fill: { color: DEEP },
      fontSize: opts.fontSize || 14,
      align: ci === 0 ? "left" : (opts.alignRest || "left"),
      valign: "middle",
      border: [
        { type: ri === 0 ? "none" : "solid", color: RULE, pt: 0.5 },
        { type: "none" },
        { type: ri === 0 ? "solid" : (ri === n - 1 ? "solid" : "none"),
          color: ri === 0 ? MUTED : RULE, pt: ri === 0 ? 1 : 0.5 },
        { type: "none" },
      ],
    },
  })));
  slide.addTable(styled, { x: opts.x, y: opts.y, w: opts.w, colW: opts.colW,
    margin: 0.07, rowH: opts.rowH || 0.36 });
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
  s.addNotes("The project asks whether an agent can know, before it runs, where to look, where not to look, and when no source will do. The talk covers the theory and what survived contact with real data; the measured results centre on the two external sources, the open web and the curated knowledge base. The code is public and appears only on the last slide.");
}

// 2 · The failure mode
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "T H E O R Y");
  title(s, "Two failures, one symptom");
  eq(s, [
    "ĉ_agree(y)  =  (1/N) Σᵢ 1{ y(τᵢ) = y },      τᵢ ~ Q(· | q)",
    "N → ∞ :      ĉ_agree  →  Q(y | q)",
  ], 0.62, 1.62, 8.8, 20);
  s.addText([
    { text: "Agreement estimates the agent's own sampling distribution, ",
      options: { color: BRIGHT } },
    { text: "not the truth.", options: { bold: true, color: REDL } },
  ], { x: 0.62, y: 3.0, w: 8.8, h: 0.8, fontSize: 17, align: "left",
       margin: 0, isTextBox: true });
  support(s, "On a question whose answer is written nowhere, every run re-reads the same absence and agrees.", 3.95, { h: 0.8 });
  s.addNotes("Start with the standard method. Self-consistency and semantic entropy run the agent N times and read agreement as confidence. As N grows, that fraction converges to Q, the agent's own sampling distribution, which equals the probability of being correct only when the proposal matches the target. Two different failures hide under one symptom. In a rare passage, the answer is in the corpus and the sampled route misses it; better retrieval fixes that. In a ghost, the answer is in no reachable corpus, so every run reads the same incomplete sources and returns the same wrong answer. Agreement is then at its maximum exactly where correctness is impossible. The two cases demand opposite responses, and from the outside they look identical.");
}

// 3 · Formalism
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "T H E O R Y");
  title(s, "Per-source formalism");
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
  s.addNotes("One corpus per source, four sources in the project: the model's parameters, the web, the knowledge base, and memory; the measured results here are for the web and the knowledge base. Two quantities per source, kept apart and never averaged. Ghost mass is the probability the true answer is not in the corpus at all. Reliability is conditional: the chance the agent finds the answer given that it is there, which makes it skill on winnable questions rather than accuracy. The conditioning is the whole point, because the two quantities indicate opposite repairs: low reliability says fix the pipeline, high ghost mass says stop searching this source. A single merged confidence cannot say which. Phi of q is computed from the question and the retrieval only, before any answer exists.");
}

// 4 · Decomposition
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "T H E O R Y");
  title(s, "Where sampling cannot reach");
  eq(s, ["U~s~(q)   =   U_alea(q)   +   U_param(q | s)   +   g~s~(q)"],
     0.62, 1.7, 8.8, 21);
  ruleTable(s, [
    ["term", "meaning", "reduced by"],
    ["U_alea", "the question is ambiguous", "asking the user"],
    ["U_param", "held, but the agent is unsure", "sampling, retrieval"],
    ["g~s~", "cannot be held", "changing source only"],
  ], { x: 0.62, y: 2.8, w: 8.8, colW: [1.7, 3.9, 3.2], fontSize: 14, accentCol: 2 });
  s.addNotes("The usual split of uncertainty is aleatoric against epistemic. Ghost mass is a third thing: epistemic about the corpus rather than the model. More samples are drawn from a corpus that does not contain the answer, so no amount of sampling moves it; only consulting a different source does. We use the additive form as a reporting convention rather than a theorem, following Kirchhof and colleagues, and estimate the ghost term operationally from labelled coverage. This is the term the standard estimators cannot see, and the reason a separate, per-source estimate is worth the trouble.");
}

// 5 · The claim
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "D E S I G N");
  title(s, "The claim is testable");
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
  support(s, "CRAG benchmark · 4,409 questions · 738 paired at five and fifty pages, agent byte-identical", 4.25, { h: 0.8 });
  s.addNotes("The strongest objection to the formalism is that ghost mass and reliability are one messy quantity split arbitrarily, and that everything called a ghost is just retrieval failing harder. The objection is testable with a double dissociation. If reliability belongs to the agent, improving the agent while the corpus is held fixed should move r and leave g alone. If ghost mass belongs to the corpus, growing the corpus while the agent is held byte-identical should move g and leave r alone. We ran both arms on CRAG: three retrieval generations for the first, and for the second the same 738 questions with five pages and then fifty, the agent unchanged to the byte. None of the fifty-seven papers in the landscape review runs this design.");
}

// 6 · Dissociation
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T S");
  title(s, "Each knob moves exactly one quantity");
  plate(s, "plate_dissociation.png", 2.415, 7.9, 5.0, 1.42);
  support(s, "Δg = −0.168, 95% CI [−0.195, −0.142]   ·   membership flips: 124 gained, 0 lost", 5.0);
  s.addNotes("The left panel is reliability, the right is ghost mass; in each pair the grey bar is before and the coloured bar is after. Improving the agent four times over moved reliability from 0.066 to 0.286 and left ghost mass flat. Growing the corpus tenfold halved ghost mass, from 0.322 to 0.154 with a confidence interval nowhere near zero, and moved reliability by eight thousandths. Each manipulation moves exactly one quantity. The validity check is the flip count: since the five-page corpus is a subset of the fifty-page one, a sound membership labeller can only gain members, never lose them. We gained 124 and lost zero. A single loss would have flagged labelling noise.");
}

// 7 · Depth
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T S");
  title(s, "Ghost mass is depth-dependent");
  plate(s, "plate_depth.png", 2.041, 6.7, 5.0, 1.4);
  support(s, "realtime: g falls 0.481 → 0.123, the largest drop of any class", 5.02);
  s.addNotes("Split the same result by how fast each question's answer changes in the world. At five pages, realtime questions carry the heaviest ghost mass, 0.481, and the natural reading is staleness: the web is out of date for things that move. At fifty pages the picture inverts. Realtime drops to 0.123 and becomes the best-covered class, a drop three times larger than for static questions. The fresh figures existed all along, just lower in the ranking than a five-page window could reach. So the apparent staleness of the web source was substantially a retrieval-depth effect, and which questions are ghosts depends on how deep the system reads. This refines the working hypothesis in the project specification, which has ghost mass growing with recency: true at shallow depth, inverted at depth.");
}

// 8 · H2
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T S");
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
    { text: "Gate: false premise at 0.868 from text alone.",
      options: { color: BRIGHT } },
  ], { x: 0.62, y: 4.15, w: 8.8, h: 0.8, fontSize: 13.5, align: "left",
       margin: 0, isTextBox: true });
  s.addNotes("The second hypothesis says cheap features, computed before any answer is generated, predict whether the answer is in the corpus. On the knowledge base it holds comfortably at 0.83. On the web at five pages it appeared refuted at 0.51, indistinguishable from the shuffled baseline. That null was a benchmark artifact: every question carries exactly five unscored pages, so the informative features were constants. With fifty pages the features vary and the same probe reaches 0.651 against the project's bar of 0.6. There is also a gate before any source matters: a plain text classifier on the question alone detects false premises at 0.868, so part of where-not-to-look is decidable before consulting anything. That is the omega component of phi.");
}

// 9 · Inversion
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T S");
  title(s, "Abstention breaks the standard estimators");
  plate(s, "plate_inversion.png", 2.395, 7.5, 5.0, 1.42);
  support(s, "conditioning on abstention: MeanTokenEntropy 0.047 → 0.966, nothing harmed", 5.0);
  s.addNotes("We measured nine standard uncertainty estimators from LM-Polygraph with isotonic calibration on a held-out split. Red dots are raw AUROC, blue are after conditioning on abstention. Headline performance looks wildly spread, from 0.034 to 0.97 on the same arm, but the spread is entirely about abstention. When the model declines to answer, it does so with near-zero token entropy, so entropy-family estimators read confident refusal as confident assertion and invert to worse than chance. Sequence log-likelihood happens to encode the same refusal as uncertain, so it looks strong. Make the encoding explicit, by assigning abstentions maximal uncertainty, and the inverted estimator repairs from 0.047 to 0.966 while nothing else is harmed. Among questions the model actually answers, every estimator sits between 0.59 and 0.67. The spread was never about discrimination.");
}

// 10 · Calibration structure
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T S");
  title(s, "The average hides the structure");
  plate(s, "plate_reliability.png", 5.087, 8.76, 5.0, 1.45);
  ruleTable(s, [
    ["expected calibration error", "value"],
    ["overall", "0.030   [0.016, 0.073]"],
    ["per KAP cell", "0.045 to 0.130"],
  ], { x: 0.62, y: 3.6, w: 8.8, colW: [4.4, 4.4], fontSize: 14, rowH: 0.4, accentCol: 1 });
  s.addNotes("Calibration measured overall looks excellent: expected calibration error of 0.030. Measured inside each KAP cell, every single cell is worse than the overall figure, from 0.045 up to 0.130. The errors cancel: overconfident where answers move, underconfident where they sit still, averaging to a number that is accurate and uninformative. The recency axis shows the same structure in the confidence-accuracy gap: 0.248 on realtime questions against 0.097 on static, with non-overlapping intervals. For completeness, marginal conformal coverage held in every cell, but that test was conservative, with coverage near one; the structure shows in calibration error, not in coverage.");
}

// 11 · Fusion
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  kicker(s, "R E S U L T S");
  title(s, "Where the ignorance mass sits");
  eq(s, [
    "product rule answers only if     r~s~  >  g~s~ / (1 − g~s~)",
    "Dempster-Shafer:     m({ŷ~s~}) = r~s~ ,      m(Θ) = 1 − r~s~",
  ], 0.62, 1.62, 8.8, 19);
  s.addText([
    { text: "K would need r > 2.7.   ", options: { color: REDL, bold: true } },
    { text: "Ignorance on Θ instead: ECE 0.102 against 0.163.",
      options: { color: BRIGHT } },
  ], { x: 0.62, y: 3.12, w: 8.8, h: 0.5, fontSize: 16.5, align: "left",
       margin: 0, isTextBox: true });
  s.addNotes("Carrying the two numbers to the decision rule exposed a defect in the fusion rule the project started from. The Bayesian product form spreads each source's ghost mass as noise over every candidate, including the one that source just proposed. Solve for when it prefers answering over silence and the condition is r greater than g over one minus g. For the knowledge base that demands reliability above 2.7, which no probability satisfies; we confirmed empirically that it silences a source that was answering correctly every time. Dempster-Shafer differs in exactly one respect: the unreliability mass is parked on the whole frame as uncommitted belief rather than spread as noise. Measured on real evidence it is the better calibrated of the two. The two conflict measures, kappa and the Bayesian evidence ratio from the cosmology literature, tied on the seventy real disagreements we hold; that question needs more conflict data. The decision rule stays answer only above one half under plus-one, zero, minus-one scoring.");
}

// 12 · Limits
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
  s.addNotes("Four results came out negative and belong in the record. Per-cell conformal added nothing here because marginal coverage already held everywhere, though the test was conservative. The memory source had essentially nothing to recall on a benchmark of unique questions; measuring it needs repeated or related queries. In the sports and finance domains, forty-four percent of questions ask for aggregates over records the graph physically holds, so the answer is derivable but never stated anywhere; the membership test records those as ghosts, inflating ghost mass with what is really a capability gap. And all reader results come from small local models, 1.5 and 7 billion parameters, so every reader number is a floor, not a ceiling. One more honest weakening: sampling is not blind to absence, it carries weak signal around 0.64, mostly through the abstention rate.");
}

// 13 · Close
{
  const s = pres.addSlide({ masterName: "DARKTITLE" });
  s.addText(runsOf("( r~s~(q) ,  g~s~(q) )", WHITE), {
    x: 0.9, y: 1.9, w: 8.2, h: 1.0, fontSize: 44, bold: true,
    fontFace: "Cambria", color: WHITE, align: "left", margin: 0, isTextBox: true });
  s.addText("per question, per source · predicted before execution · carried unmerged to the decision rule", {
    x: 0.92, y: 3.05, w: 8.2, h: 0.8, fontSize: 15, color: BODY,
    align: "left", margin: 0, isTextBox: true });
  s.addText("github.com/shecode-hue/knowing-where-not-to-look", {
    x: 0.92, y: 4.75, w: 8.2, h: 0.4, fontSize: 13, color: MUTED,
    align: "left", margin: 0, isTextBox: true });
  s.addNotes("What the project hands to the fusion stage is an interface, not a tool: for each question and each source, a predicted reliability and a predicted ghost mass, computed before execution and carried unmerged into whatever fusion rule the decision stage prefers. Behind it stand both halves of the independence experiment with intervals and a passed monotonicity check, a one-line repair for abstention-inverted estimators that is portable to any abstaining system, and the depth result that reinterprets staleness. Open items: a frontier reader for the scaling column, the remaining fifty-page pairs, and more web-against-knowledge-base disagreements to settle the conflict-measure question. Code, data preparation and every result table are in the repository.");
}

(async () => {
  await pres.writeFile({ fileName: "knowing_where_not_to_look.pptx" });
  await applyTheme("knowing_where_not_to_look.pptx", THEME);
  console.log("deck written");
})();
