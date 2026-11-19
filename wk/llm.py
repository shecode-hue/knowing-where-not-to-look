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


def complete(prompt, n=48, temperature=0.0, logprobs=False, seed=0):
    body = {"prompt": prompt, "n_predict": n, "temperature": temperature,
            "seed": seed, "cache_prompt": True,
            "stop": ["\n\n", "Question:", "Evidence:"]}
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


def retracted(said):
    return NO_ANSWER.lower() in (said or "").lower()


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


def _shape(said, out):
    gave_up = retracted(said)
    return {"answer": None if gave_up else said, "raw": said,
            "mean_logprob": mean_logprob(out), "abstained": gave_up}


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
