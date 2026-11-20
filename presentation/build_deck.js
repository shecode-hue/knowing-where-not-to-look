// Science-first workshop deck for the W and K subgroup.
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("./apply_theme.js");

const FIG = "/Users/shainmukungu/Desktop/knowing_where_not_to_look/results/figures/";

const INK = "1A1A1C";
const NAVY = "1C4A80";
const DEEP = "16304F";
const RED = "B2303A";
const GREY = "6C6E74";
const LINE = "D7D4D0";
const WASH = "F4F3F1";
const WHITE = "FFFFFF";

const THEME = {
  name: "Knowing Where Not to Look",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: INK, lt1: WHITE, dk2: NAVY, lt2: "F2F2F2",
    accent1: NAVY, accent2: RED, accent3: GREY, accent4: "84B59F",
    accent5: "50808E", accent6: "B85042", hlink: NAVY, folHlink: GREY,
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Shain Kampasi Mukungu";
pres.title = "Knowing Where Not to Look";

pres.defineSlideMaster({
  title: "DARK",
  background: { color: DEEP },
  objects: [],
});

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: WHITE },
  objects: [
    { placeholder: {
        options: { name: "title", type: "title", x: 0.5, y: 0.26, w: 9.0,
                   h: 0.55, fontSize: 21, bold: true, color: INK,
                   align: "left", margin: 0 },
        text: "" } },
    { text: { text: "Knowing Where Not to Look",
              options: { x: 0.5, y: 5.28, w: 4.0, h: 0.22, fontSize: 8,
                         color: GREY, align: "left", margin: 0 } } },
  ],
  slideNumber: { x: 9.05, y: 5.26, w: 0.6, fontSize: 8, color: GREY, align: "right" },
});

function eqBox(slide, lines, x, y, w, h, size) {
  slide.addShape(pres.ShapeType.rect, {
    x, y, w, h, fill: { color: WASH }, line: { color: LINE, width: 0.75 },
  });
  slide.addText(
    lines.map((t, i) => ({
      text: t, options: { breakLine: i < lines.length - 1 },
    })),
    { x: x + 0.18, y, w: w - 0.36, h, fontSize: size || 13,
      fontFace: "Cambria", color: INK, align: "left", valign: "middle",
      margin: 0, isTextBox: true, lineSpacingMultiple: 1.25 });
}

function bullets(slide, items, x, y, w, h, size) {
  slide.addText(
    items.map((t, i) => ({
      text: t,
      options: { bullet: { code: "2022", indent: 12 },
                 breakLine: i < items.length - 1 },
    })),
    { x, y, w, h, fontSize: size || 13.5, color: INK, align: "left",
      valign: "top", margin: 0, isTextBox: true, paraSpaceAfter: 7 });
}

function table(slide, rows, opts) {
  const styled = rows.map((row, ri) => row.map((cell) => ({
    text: cell,
    options: {
      bold: ri === 0,
      color: ri === 0 ? WHITE : INK,
      fill: { color: ri === 0 ? NAVY : (ri % 2 ? WHITE : "FAFAF8") },
      fontSize: opts.fontSize || 12,
      align: "left", valign: "middle",
    },
  })));
  slide.addTable(styled, {
    x: opts.x, y: opts.y, w: opts.w, colW: opts.colW,
    border: { type: "solid", color: LINE, pt: 0.5 },
    margin: 0.06,
  });
}

// 1. Title
{
  const s = pres.addSlide({ masterName: "DARK" });
  s.addText("Knowing Where Not to Look", {
    x: 0.7, y: 1.55, w: 8.6, h: 0.9, fontSize: 40, bold: true,
    color: WHITE, align: "left", margin: 0, isTextBox: true });
  s.addText("Query- and source-resolved confidence for agents", {
    x: 0.7, y: 2.5, w: 8.6, h: 0.5, fontSize: 19, color: "CADCFC",
    align: "left", margin: 0, isTextBox: true });
  s.addText(
    [{ text: "W and K subgroup: the open web and the curated knowledge base",
       options: { breakLine: true } },
     { text: "AI, Uncertainty and Simulation · Mauritius · 20 November 2026",
       options: {} }],
    { x: 0.7, y: 4.35, w: 8.6, h: 0.7, fontSize: 13, color: "9FB6D8",
      align: "left", margin: 0, isTextBox: true, lineSpacingMultiple: 1.3 });
  s.addNotes("Subgroup scope: the two external sources, W and K. The talk is the theory and what survived measurement.");
}

// 2. The failure mode
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Two failures, one symptom", { placeholder: "title" });
  eqBox(s, [
    "ĉ_agree(y) = (1/N) Σᵢ 1{ y(τᵢ) = y },   τᵢ ~ Q(·|q)",
    "N → ∞ :   ĉ_agree → Q(y|q)   (the agent's sampling distribution, not Pr(y = y*))",
  ], 0.5, 1.0, 9.0, 0.95, 13);
  bullets(s, [
    "Rare passage: the answer is in the corpus and the sampled route misses it. Better retrieval fixes it.",
    "Ghost: the answer is in no reachable corpus. Every run re-reads the same absence.",
    "Agreement-based confidence is therefore maximal exactly where correctness is impossible.",
    "The two causes are indistinguishable from outside the system, and they demand opposite responses.",
  ], 0.5, 2.25, 9.0, 2.6, 14);
  s.addNotes("Self-consistency and semantic entropy estimate the proposal Q, not the target. On a ghost question the proposal concentrates on the same wrong answer in every run.");
}

// 3. Formalism
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Per-source formalism", { placeholder: "title" });
  eqBox(s, [
    "s ∈ {P, W, K, M},  each with corpus Cₛ",
    "gₛ(q) = Pr( y* ∉ Cₛ | φ(q) )                     ghost mass",
    "rₛ(q) = Pr( ŷₛ = y* | y* ∈ Cₛ , φ(q) )        reliability",
    "λₛ = 1 − rₛ                                   rare-passage mass",
  ], 0.5, 1.0, 9.0, 1.45, 13);
  table(s, [
    ["class", "condition", "indicated action"],
    ["covered", "y* ∈ Cₛ and the agent reaches it", "answer"],
    ["rare passage", "y* ∈ Cₛ and the agent misses it", "repair retrieval"],
    ["ghost", "y* ∉ Cₛ", "change source or abstain"],
  ], { x: 0.5, y: 2.72, w: 9.0, colW: [1.7, 4.3, 3.0], fontSize: 12.5 });
  s.addText("φ(q): features of the question and the retrieval only, available before the agent runs. The conditioning in r is the point: r is skill on winnable questions, not accuracy.", {
    x: 0.5, y: 4.55, w: 9.0, h: 0.75, fontSize: 12.5, color: GREY,
    align: "left", margin: 0, isTextBox: true });
  s.addNotes("Keeping g and r separate is the whole project: a single confidence cannot say which repair is indicated.");
}

// 4. Decomposition
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Where sampling cannot reach", { placeholder: "title" });
  eqBox(s, [
    "Uₛ(q)  =  U_alea(q)  +  U_param(q | s)  +  gₛ(q)",
  ], 0.5, 1.05, 9.0, 0.62, 14);
  table(s, [
    ["term", "interpretation", "reduced by"],
    ["U_alea", "the question is ambiguous", "asking the user"],
    ["U_param", "the source holds it, the agent is unsure", "sampling, better retrieval"],
    ["gₛ", "the source cannot hold it", "changing source, nothing else"],
  ], { x: 0.5, y: 1.95, w: 9.0, colW: [1.5, 4.3, 3.2], fontSize: 12.5 });
  s.addText("Additive form used as a reporting convention, not a theorem (Kirchhof et al. 2025). gₛ is defined operationally and estimated from labelled coverage.", {
    x: 0.5, y: 3.8, w: 9.0, h: 0.6, fontSize: 12.5, color: GREY,
    align: "left", margin: 0, isTextBox: true });
  s.addNotes("The third term is the contribution. More samples are drawn from a corpus that does not contain the answer, so no amount of sampling moves g.");
}

// 5. The testable claim
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("The testable claim: r and g belong to different objects", { placeholder: "title" });
  s.addText("Objection: these are one quantity split arbitrarily, and every ghost is retrieval failing harder. The objection is testable by a double dissociation.", {
    x: 0.5, y: 1.0, w: 9.0, h: 0.6, fontSize: 13.5, color: INK,
    align: "left", margin: 0, isTextBox: true });
  table(s, [
    ["manipulation", "prediction if r is the agent's and g is the corpus's"],
    ["improve the agent, hold the corpus fixed", "r rises, g unchanged"],
    ["grow the corpus, hold the agent fixed", "g falls, r unchanged"],
  ], { x: 0.5, y: 1.85, w: 9.0, colW: [4.2, 4.8], fontSize: 13 });
  bullets(s, [
    "CRAG benchmark, 4,409 real questions, five domains, labelled recency and popularity.",
    "Agent arm: three retrieval generations, corpus fixed at five pages per question.",
    "Corpus arm: 738 paired questions at five and at fifty pages, agent byte-identical.",
  ], 0.5, 3.35, 9.0, 1.7, 13);
  s.addNotes("Design, not anecdote: each arm moves one knob. None of the 57 papers in the landscape review runs this.");
}

// 6. Dissociation result
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Result: the double dissociation", { placeholder: "title" });
  s.addImage({ path: FIG + "dissociation.png", x: 0.72, y: 1.0, w: 8.56, h: 3.76 });
  s.addText("Corpus arm change in g: −0.168, 95% CI [−0.195, −0.142]. Validity: membership flips 124 gained, 0 lost, the monotonicity a sound labeller must show.", {
    x: 0.5, y: 4.80, w: 8.4, h: 0.56, fontSize: 12, color: GREY,
    align: "left", margin: 0, isTextBox: true });
  s.addNotes("Agent improved four times: r 0.066 to 0.286, g flat. Corpus times ten: g 0.322 to 0.154, r moves 0.008. Each knob moves exactly one quantity.");
}

// 7. Depth effect
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Ghost mass is depth-dependent", { placeholder: "title" });
  s.addImage({ path: FIG + "depth_effect.png", x: 0.6, y: 1.0, w: 6.1, h: 3.39 });
  bullets(s, [
    "Realtime: g falls 0.481 to 0.123, the largest drop of any class.",
    "At five pages, recency reads as staleness.",
    "At fifty pages, realtime is the best-covered class: the fresh figures exist lower in the ranking.",
    "Which questions are ghosts depends on how deep the system reads.",
  ], 6.9, 1.15, 2.7, 3.6, 12);
  s.addNotes("Refines the working hypothesis that ghost mass grows with recency: true at shallow depth, inverted at depth. Staleness was substantially a retrieval-depth effect.");
}

// 8. H2
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Membership is predictable before execution", { placeholder: "title" });
  table(s, [
    ["source", "AUROC, answer-in-corpus", "permutation baseline"],
    ["K, knowledge graph", "0.83", "0.49"],
    ["W, five pages", "0.51", "0.50"],
    ["W, fifty pages", "0.651", "0.484"],
  ], { x: 0.5, y: 1.05, w: 9.0, colW: [3.2, 3.2, 2.6], fontSize: 13 });
  bullets(s, [
    "Hypothesis bar: 0.6. Features are question-side and retrieval-side only, computed before any answer exists.",
    "The five-page null was a benchmark artifact: every question carried exactly five unscored pages, so the informative features were constants.",
    "A question-text classifier alone detects false premises at AUROC 0.868, so part of where-not-to-look is decidable before any source is consulted.",
  ], 0.5, 2.95, 9.0, 2.2, 13);
  s.addNotes("H2 holds on both sources once the corpus varies. The gate result is the omega component of phi(q).");
}

// 9. Estimators and the inversion
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Standard estimators under proper scoring rules", { placeholder: "title" });
  s.addImage({ path: FIG + "inversion_repair.png", x: 0.55, y: 1.0, w: 6.2, h: 2.9 });
  bullets(s, [
    "Nine LM-Polygraph estimators, isotonic calibration on a 40% split, held-out test.",
    "Overall ranking is strong: P(True) 0.81 to 0.98 across arms.",
    "The entropy family inverts: an abstention has near-zero token entropy, so confident refusal reads as confident assertion.",
    "Conditioning on abstention repairs MeanTokenEntropy from 0.047 to 0.966 and harms nothing.",
    "Among answered questions every estimator sits at 0.59 to 0.67.",
  ], 6.95, 1.05, 2.6, 4.1, 11);
  s.addNotes("The spread in headline AUROC is entirely how each estimator happens to encode an abstention. Discrimination given engagement is uniformly modest.");
}

// 10. Calibration structure
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Calibration has structure the average hides", { placeholder: "title" });
  s.addImage({ path: FIG + "reliability_by_cell.png", x: 0.5, y: 1.0, w: 9.0, h: 2.01 });
  table(s, [
    ["quantity", "overall", "per cell"],
    ["ECE, P(True), concatenation arm", "0.030  [0.016, 0.073]", "0.045 to 0.130"],
    ["confidence minus accuracy, by recency", "static 0.097  [0.038, 0.156]", "realtime 0.248  [0.155, 0.355]"],
  ], { x: 0.5, y: 3.3, w: 9.0, colW: [3.7, 2.8, 2.5], fontSize: 12 });
  s.addText("Errors cancel across cells: overconfident where answers move, underconfident where they sit still. The marginal number is accurate and uninformative.", {
    x: 0.5, y: 4.72, w: 8.4, h: 0.56, fontSize: 12, color: GREY,
    align: "left", margin: 0, isTextBox: true });
  s.addNotes("H1 holds on the recency axis with non-overlapping intervals, and fails on popularity and hops. Marginal conformal coverage held in every cell, a conservative test; the structure shows in ECE, not coverage.");
}

// 11. Fusion
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Fusion: where the ignorance mass sits decides everything", { placeholder: "title" });
  eqBox(s, [
    "product rule answers only if   rₛ > gₛ / (1 − gₛ)       K would need r > 2.7",
    "Dempster-Shafer:   m({ŷₛ}) = rₛ ,   m(Θ) = 1 − rₛ      ignorance parked on Θ",
    "decision:   answer ŷ  ⟺  p(ŷ | e) > 1/2   under +1 / 0 / −1 scoring",
  ], 0.5, 1.0, 9.0, 1.5, 13);
  bullets(s, [
    "The published product rule spreads g·u(y) over every candidate, so a high-ghost source endorses its own guess; solved, it can never answer. Confirmed empirically before correction.",
    "Measured on real W-K evidence: Dempster-Shafer better calibrated, ECE 0.102 against 0.163.",
    "Conflict measures tied on 70 real disagreements: κ 0.657, Bayesian evidence ratio 0.650.",
  ], 0.5, 2.8, 9.0, 2.2, 13);
  s.addNotes("The degeneracy went unnoticed because no prior work carries g and r separately to the decision rule, which is the gap the project names.");
}

// 12. Negative results
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("Negative results, stated as results", { placeholder: "title" });
  bullets(s, [
    "H4 refuted on this data: marginal conformal met 90% coverage in every KAP cell, so per-cell calibration added nothing. The test was conservative, coverage near 1.0.",
    "Memory source: g = 0.995 on unique queries. Nothing to recall; measuring M needs repeated or related questions.",
    "A third class is miscounted as ghost: derivable but never stated. 44% of sports questions need aggregation over records the graph holds.",
    "Readers are small local models; every reader figure is a floor. The 38% of in-corpus answers beyond the agent's 400-span window decompose λ into view and ranking.",
  ], 0.5, 1.1, 9.0, 3.9, 13.5);
  s.addNotes("The sampling premise also weakened honestly: agreement carries weak signal about absence, AUROC 0.64, mostly through the abstention rate.");
}

// 13. Close
{
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText("What this hands the next stage", { placeholder: "title" });
  bullets(s, [
    "The interface: per-question, per-source (rₛ, gₛ), predicted before execution, carried unmerged to the decision rule.",
    "Both halves of the independence experiment, with intervals and a passed monotonicity check.",
    "A one-line repair for abstention-inverted estimators, portable to any abstaining system.",
    "Open: a frontier reader for the scaling column, the remaining fifty-page pairs, more W-K disagreements for the conflict question.",
  ], 0.5, 1.15, 9.0, 3.2, 14);
  s.addText("Code and results: github.com/shecode-hue/knowing-where-not-to-look", {
    x: 0.5, y: 4.75, w: 9.0, h: 0.4, fontSize: 12.5, color: NAVY,
    align: "left", margin: 0, isTextBox: true });
  s.addNotes("Close on the interface, not the tool. Questions welcome on any of the estimators or the experiment design.");
}

(async () => {
  await pres.writeFile({ fileName: "wk_subgroup.pptx" });
  await applyTheme("wk_subgroup.pptx", THEME);
  console.log("deck written: wk_subgroup.pptx");
})();
