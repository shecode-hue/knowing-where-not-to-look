"""Write the first-page text of every downloaded paper to abstracts.txt."""
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
out = []
for pdf in sorted(HERE.glob("*.pdf")):
    text = subprocess.run(["pdftotext", "-l", "1", str(pdf), "-"],
                          capture_output=True, text=True).stdout
    out.append(f"=== {pdf.stem}\n{' '.join(text.split())[:1300]}\n")
(HERE / "abstracts.txt").write_text("\n".join(out))
print(len(out), "papers")
