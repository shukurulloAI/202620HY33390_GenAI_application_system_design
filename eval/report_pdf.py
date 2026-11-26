"""
Build docs/REPORT.pdf from docs/REPORT.md (Markdown -> HTML -> headless Chrome).

    python -m eval.report_pdf                     # docs/REPORT.md -> docs/REPORT.pdf
    python -m eval.report_pdf docs/X.md out.pdf

Needs `pip install markdown` and Google Chrome (or Chromium) installed. Images are linked
relative to the Markdown file (docs/figures/...).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHROMES = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "google-chrome", "chromium", "chromium-browser"]

CSS = """
@page { size: A4; margin: 18mm 17mm 18mm 17mm; }
body { font-family: "Apple SD Gothic Neo", "Noto Sans KR", Arial, sans-serif; font-size: 10.2pt;
       line-height: 1.45; color: #1d1d1b; }
h1 { font-size: 20pt; margin: 0 0 4pt 0; }
h2 { font-size: 14pt; margin: 18pt 0 6pt 0; border-bottom: 1px solid #d9d8d3; padding-bottom: 3pt;
     page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt 0; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
table { border-collapse: collapse; margin: 6pt 0 10pt 0; font-size: 9pt; width: 100%;
        page-break-inside: avoid; }
th, td { border: 1px solid #d9d8d3; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #f1f0ec; }
code { font-family: Menlo, monospace; font-size: 8.6pt; background: #f4f3ef; padding: 0 2pt; }
pre { background: #f4f3ef; padding: 6pt; font-size: 8.4pt; white-space: pre-wrap;
      page-break-inside: avoid; }
img { max-width: 100%; display: block; margin: 6pt auto; page-break-inside: avoid; }
blockquote { border-left: 3px solid #2a78d6; margin: 6pt 0; padding: 2pt 10pt; color: #3d3c39; }
.subtitle { color: #52514e; margin-bottom: 14pt; }
"""


def chrome() -> str:
    for candidate in CHROMES:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    raise SystemExit("Google Chrome or Chromium is needed to print the PDF")


def build(source: Path, target: Path) -> Path:
    import markdown
    body = markdown.markdown(source.read_text(encoding="utf-8"),
                             extensions=["tables", "fenced_code", "toc", "sane_lists"])
    html = (f"<!doctype html><html><head><meta charset='utf-8'><title>{source.stem}</title>"
            f"<base href='{source.parent.resolve().as_uri()}/'><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "report.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run([chrome(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        "--allow-file-access-from-files", f"--print-to-pdf={target.resolve()}",
                        page.as_uri()], check=True, capture_output=True, timeout=120)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", nargs="?", type=Path, default=ROOT / "docs" / "REPORT.md")
    parser.add_argument("target", nargs="?", type=Path)
    args = parser.parse_args()
    target = args.target or args.source.with_suffix(".pdf")
    print(build(args.source, target))


if __name__ == "__main__":
    main()
