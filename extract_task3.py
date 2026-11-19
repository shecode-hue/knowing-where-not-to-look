"""Stream the truncated task-3 archive and keep matched questions, HTML pre-stripped."""
import bz2
import json
import pickle
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from wk.crag import strip_html

PART = ROOT / "data" / "task3" / "part0"
OUT = ROOT / "data" / "task3" / "task3_matched.jsonl.bz2"
RESULTS = ROOT / "results"


def wanted_qids():
    rows = pickle.load(open(RESULTS / "scored_W.pkl", "rb"))
    return {r["qid"] for r in rows}


def slim(item):
    pages = item.get("search_results") or []
    kept = []
    for p in pages:
        if not isinstance(p, dict):
            continue
        body = strip_html(p.get("page_result") or p.get("page_content"))
        kept.append({"page_name": str(p.get("page_name") or ""),
                     "page_url": str(p.get("page_url") or ""),
                     "page_snippet": strip_html(p.get("page_snippet")),
                     "page_last_modified": str(p.get("page_last_modified")
                                               or ""),
                     "page_result": body})
    out = {k: v for k, v in item.items() if k != "search_results"}
    out["search_results"] = kept
    return out


def main():
    want = wanted_qids()
    print(f"{len(want)} qids wanted", flush=True)
    t0, seen, kept, lines = time.time(), 0, 0, 0
    sink = bz2.open(OUT, "wt")
    try:
        stream = bz2.open(PART, "rb")
        tar = tarfile.open(fileobj=stream, mode="r|")
        for member in tar:
            if not member.name.endswith((".jsonl", ".json")):
                continue
            print(f"member {member.name} ({member.size / 1e6:.0f} MB raw)",
                  flush=True)
            fh = tar.extractfile(member)
            if fh is None:
                continue
            buf = b""
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    lines += 1
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    seen += 1
                    qid = str(item.get("interaction_id") or "")
                    if qid in want:
                        sink.write(json.dumps(slim(item)) + "\n")
                        kept += 1
                    if seen % 100 == 0:
                        print(f"  {seen} items, kept {kept}, "
                              f"{time.time() - t0:.0f}s", flush=True)
    except (EOFError, OSError, tarfile.ReadError) as e:
        print(f"stream ended ({type(e).__name__}), as expected for a "
              f"truncated part", flush=True)
    finally:
        sink.close()
    print(f"done: {seen} items seen, {kept} matched -> {OUT} "
          f"({OUT.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f}s)",
          flush=True)


if __name__ == "__main__":
    main()
