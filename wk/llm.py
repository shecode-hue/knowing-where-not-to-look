"""Local llama.cpp client, plus the reader and parametric prompts."""
import json
import math
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
HOST = os.environ.get("LLM_HOST", "127.0.0.1")
PORT = int(os.environ.get("LLM_PORT", "8081"))
BASE = f"http://{HOST}:{PORT}"
NO_ANSWER = "UNKNOWN"
_proc = None

READER = """You answer questions from supplied evidence only.

Rules:
- Use only the evidence. Never use your own knowledge.
- Answer in as few words as possible: a name, a number, a date, a list.
- If the evidence does not contain the answer, reply exactly {no}.
- If the question assumes something false, reply exactly {no}.

Evidence:
{evidence}

Question: {question}
Answer:"""

PARAMETRIC = """Answer the question from your own knowledge.

Rules:
- Answer in as few words as possible: a name, a number, a date, a list.
- If you do not know, or your knowledge may be out of date, reply exactly {no}.
- Never guess.

Question: {question}
Answer:"""


def model_path():
    found = sorted(MODELS.glob("*.gguf"))
    if not found:
        raise FileNotFoundError(f"no .gguf model in {MODELS}")
    return found[-1]


def alive():
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start(ctx=4096, wait=900):
    global _proc
    if alive():
        return True
    cmd = ["llama-server", "-m", str(model_path()), "--host", HOST,
           "--port", str(PORT), "-c", str(ctx), "-ngl", "99",
           "--parallel", "1"]
    _proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    for _ in range(wait):
        if alive():
            return True
        if _proc.poll() is not None:
            raise RuntimeError("llama-server exited during startup")
        time.sleep(1)
    raise TimeoutError("llama-server did not become ready")


def stop():
    global _proc
    if _proc is not None and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None


def complete(prompt, n=48, temperature=0.0, logprobs=False, seed=0,
             stop=None):
    body = {"prompt": prompt, "n_predict": n, "temperature": temperature,
            "seed": seed, "cache_prompt": True,
            "stop": ["\n\n", "Question:", "Evidence:", NO_ANSWER]
            if stop is None else stop}
    if logprobs:
        body["n_probs"] = 5
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}/completion", data=data,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def clean(text):
    text = (text or "").strip()
    text = re.split(r"\n", text)[0].strip()
    return re.sub(r'^["\']|["\'\.]$', "", text).strip()


def strip_marker(said):
    text = (said or "").strip()
    low = text.lower()
    idx = low.find(NO_ANSWER.lower())
    if idx < 0:
        return text, False
    before = re.sub(r'[\s\.,;:\-]+$', "", text[:idx]).strip()
    return before, not before


def mean_logprob(result):
    steps = result.get("completion_probabilities") or []
    picked = []
    for step in steps:
        top = step.get("top_logprobs") or step.get("probs") or []
        if not top:
            continue
        first = top[0]
        if "logprob" in first:
            picked.append(float(first["logprob"]))
        elif float(first.get("prob", 0)) > 0:
            picked.append(math.log(float(first["prob"])))
    return sum(picked) / len(picked) if picked else float("nan")


VERBALISED = """Answer the question, then state your confidence.

Reply on two lines, exactly:
ANSWER: <your answer, or {no}>
CONFIDENCE: <a number from 0 to 100>

{context}Question: {question}
"""

PTRUE = """Question: {question}
Proposed answer: {answer}

Is the proposed answer correct? Reply with one word, True or False.
Answer:"""


def token_logprobs(result):
    steps = result.get("completion_probabilities") or []
    out = []
    for step in steps:
        top = step.get("top_logprobs") or step.get("probs") or []
        if not top:
            continue
        first = top[0]
        if "logprob" in first:
            out.append(float(first["logprob"]))
        elif float(first.get("prob", 0)) > 0:
            out.append(math.log(float(first["prob"])))
    return out


def token_entropies(result):
    steps = result.get("completion_probabilities") or []
    out = []
    for step in steps:
        top = step.get("top_logprobs") or step.get("probs") or []
        ps = []
        for cand in top:
            if "logprob" in cand:
                ps.append(math.exp(float(cand["logprob"])))
            elif "prob" in cand:
                ps.append(float(cand["prob"]))
        total = sum(ps)
        if total <= 0:
            continue
        ps = [p / total for p in ps]
        out.append(-sum(p * math.log(p) for p in ps if p > 0))
    return out


def verbalised(question, passages=None, seed=0):
    context = ""
    if passages:
        joined = "\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages))
        context = f"Evidence:\n{joined}\n\n"
    prompt = VERBALISED.format(question=question, context=context,
                               no=NO_ANSWER)
    out = complete(prompt, n=64, temperature=0.0, seed=seed,
                   stop=["Question:", "Evidence:", "\nANSWER:"])
    text = out.get("content") or ""
    answer, conf = None, None
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("answer:"):
            answer = clean(line.split(":", 1)[1])
        elif low.startswith("confidence:"):
            digits = re.findall(r"\d+(?:\.\d+)?", line)
            if digits:
                conf = min(max(float(digits[0]) / 100.0, 0.0), 1.0)
    if conf is None:
        digits = re.findall(r"(?i)confidence\D{0,12}(\d+(?:\.\d+)?)", text)
        if digits:
            conf = min(max(float(digits[0]) / 100.0, 0.0), 1.0)
    if answer:
        answer, blank = strip_marker(answer)
        if blank:
            answer = None
    return {"answer": answer, "confidence": conf, "raw": text.strip()}


def p_true(question, answer, seed=0):
    if not answer:
        return 0.0
    out = complete(PTRUE.format(question=question, answer=answer),
                   n=4, temperature=0.0, logprobs=True, seed=seed)
    said = (out.get("content") or "").strip().lower()
    lp = token_logprobs(out)
    p = math.exp(lp[0]) if lp else 0.5
    return p if said.startswith("true") else 1.0 - p


def _shape(said, out):
    answer, gave_up = strip_marker(said)
    return {"answer": None if gave_up else (answer or None), "raw": said,
            "mean_logprob": mean_logprob(out), "abstained": gave_up,
            "logprobs": token_logprobs(out),
            "entropies": token_entropies(out)}


def read(question, passages, n_evidence=6, seed=0, temperature=0.0):
    joined = "\n".join(f"[{i + 1}] {p}" for i, p in
                       enumerate(passages[:n_evidence]))
    prompt = READER.format(evidence=joined or "(none)", question=question,
                           no=NO_ANSWER)
    out = complete(prompt, logprobs=True, seed=seed, temperature=temperature)
    return _shape(clean(out.get("content")), out)


def recall(question, seed=0, temperature=0.0):
    prompt = PARAMETRIC.format(question=question, no=NO_ANSWER)
    out = complete(prompt, logprobs=True, seed=seed, temperature=temperature)
    return _shape(clean(out.get("content")), out)
