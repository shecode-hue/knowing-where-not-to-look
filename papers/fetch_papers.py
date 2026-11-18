"""Download every arXiv paper cited in the landscape review, verifying each PDF."""
import pathlib
import subprocess
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
IDS = """2211.08411 2305.12616 2402.10978 2405.01563 2405.20947 2406.02543
2406.09714 2406.12673 2406.15927 2410.07176 2410.22954 2411.00640 2411.06037
2412.01033 2412.12472 2501.12835 2502.12964 2503.01747 2504.13079 2504.19254
2505.22655 2506.09038 2506.09669 2506.17419 2506.20978 2507.06196 2508.14496
2509.04664 2509.10625 2509.21199 2511.01409 2511.04418 2512.14801 2601.15703
2601.20126 2602.01285 2602.05073 2602.06948 2603.05909 2604.03904 2604.13991
2604.20854 2605.00939 2605.24756 2606.24428 2607.07380 2607.10059 2607.10491
2607.10562 2607.17535 2607.22962 2608.00422 2609.00760 2609.04445 2609.07395
2610.27406 2611.14320""".split()


def valid(path):
    if not path.exists() or path.stat().st_size < 20000:
        return False
    with open(path, "rb") as f:
        if f.read(5) != b"%PDF-":
            return False
    out = subprocess.run(["pdftotext", "-l", "1", str(path), "-"],
                         capture_output=True)
    return out.returncode == 0 and len(out.stdout) > 200


def fetch(arxiv_id):
    dest = HERE / f"{arxiv_id}.pdf"
    for attempt in range(6):
        if valid(dest):
            return "ok"
        try:
            req = urllib.request.Request(
                f"https://arxiv.org/pdf/{arxiv_id}",
                headers={"User-Agent": "Mozilla/5.0 (research reading list)"})
            with urllib.request.urlopen(req, timeout=90) as r:
                dest.write_bytes(r.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return "NOT FOUND on arXiv"
            time.sleep(4)
        except Exception:
            time.sleep(4)
        time.sleep(1.5)
    return "ok" if valid(dest) else "FAILED after retries"


for i, arxiv_id in enumerate(IDS, 1):
    print(f"{i:2d}/{len(IDS)}  {arxiv_id}  {fetch(arxiv_id)}", flush=True)
