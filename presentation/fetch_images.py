"""Fetch openly licensed photographs from Wikimedia Commons, license-checked."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent / "images"
API = "https://commons.wikimedia.org/w/api.php"
OK_LICENSE = ("pd", "cc0", "cc by", "cc-by", "cc by-sa", "cc-by-sa")
WANT = {
    "title": "Paranal observatory night sky milky way",
    "problem": "Trinity College Library Long Room",
    "close": "VLT laser guide star night",
}
HEADERS = {"User-Agent": "kwntl-workshop-deck/1.0 (contact: workshop use)"}


def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def candidates(query):
    data = api({
        "action": "query", "format": "json",
        "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": 12,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size",
        "iiurlwidth": 2200,
    })
    pages = (data.get("query") or {}).get("pages") or {}
    out = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = str((meta.get("LicenseShortName") or {}).get("value", "")).lower()
        artist = str((meta.get("Artist") or {}).get("value", ""))
        if not any(k in lic for k in OK_LICENSE):
            continue
        if info.get("width", 0) < 1600:
            continue
        out.append({
            "title": page.get("title", ""),
            "url": info.get("thumburl") or info.get("url"),
            "license": lic,
            "artist": artist,
            "width": info.get("width"),
        })
    return out


def fetch(name, query):
    for cand in candidates(query):
        try:
            req = urllib.request.Request(cand["url"], headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as r:
                blob = r.read()
            path = OUT / f"{name}.jpg"
            path.write_bytes(blob)
            img = Image.open(path)
            img.verify()
            img = Image.open(path)
            if img.size[0] < 1200:
                continue
            print(f"  {name}: {cand['title']} ({img.size[0]}x{img.size[1]}, "
                  f"{cand['license']})")
            return {"file": path.name, "source": cand["title"],
                    "license": cand["license"],
                    "artist": cand["artist"][:160],
                    "size": list(img.size)}
        except Exception as e:
            print(f"  {name}: candidate failed ({type(e).__name__}), trying next")
    print(f"  {name}: nothing usable found")
    return None


def main():
    OUT.mkdir(exist_ok=True)
    credits = {}
    for name, query in WANT.items():
        got = fetch(name, query)
        if got:
            credits[name] = got
    json.dump(credits, open(OUT / "credits.json", "w"), indent=2)
    print(f"{len(credits)} images -> {OUT}")


if __name__ == "__main__":
    main()
