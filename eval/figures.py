"""
Figures for the report (PLAN.md §7.5, §12), as PNG files in docs/figures/.

    python -m eval.figures heatmap <report name> [--out docs/figures/heatmap_<name>.png]
    python -m eval.figures ablation <report name>=<label> ... --out docs/figures/ablation.png
    python -m eval.figures retrieval experiments/results/dev/E9 ... --out docs/figures/retrieval.png

Colours: the reference palette of the dataviz method (one blue ramp for counts; blue and
orange as the first two categorical slots), printed values on every mark, so nothing is
read from colour alone.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "eval" / "reports"
FIGURES = ROOT / "docs" / "figures"

SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
STAGES = ["router", "retrieval", "schedule_tool", "gate", "generation", "validation", "other"]

plt.rcParams.update({"font.family": ["Apple SD Gothic Neo", "AppleGothic", "Noto Sans CJK KR",
                                     "DejaVu Sans"],
                     "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
                     "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "savefig.facecolor": SURFACE, "axes.spines.top": False,
                     "axes.spines.right": False})


def _report(name: str) -> dict:
    return json.loads((REPORTS / name / "report.json").read_text(encoding="utf-8"))


def heatmap(name: str, out: Path, title: str | None = None) -> Path:
    report = _report(name)
    heat = report["failure_heatmap"]
    slices = sorted(report["by_slice"])
    stages = [s for s in STAGES if any(heat.get(sl, {}).get(s) for sl in slices)]
    values = [[heat.get(sl, {}).get(st, 0) for st in stages] for sl in slices]
    peak = max((v for row in values for v in row), default=1) or 1
    cmap = LinearSegmentedColormap.from_list("blue", RAMP)
    fig, ax = plt.subplots(figsize=(1.3 * len(stages) + 2.6, 0.42 * len(slices) + 1.4))
    for i, row in enumerate(values):
        for j, value in enumerate(row):
            if value:
                share = value / peak
                ax.add_patch(plt.Rectangle((j + 0.03, i + 0.03), 0.94, 0.94,
                                           color=cmap(0.15 + 0.85 * share), lw=0))
                ax.text(j + 0.5, i + 0.5, str(value), ha="center", va="center",
                        color="white" if share > 0.45 else INK, fontsize=10)
    totals = [report["by_slice"][sl]["cases"] for sl in slices]
    ax.set_xlim(0, len(stages))
    ax.set_ylim(len(slices), 0)
    ax.set_xticks([j + 0.5 for j in range(len(stages))], stages)
    ax.set_yticks([i + 0.5 for i in range(len(slices))],
                  [f"{sl} (n={n})" for sl, n in zip(slices, totals, strict=True)])
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.xaxis.tick_top()
    failed = sum(v for row in values for v in row)
    ax.set_title(title or f"Earliest failed stage, {failed} failed cases ({name})",
                 loc="left", fontsize=11, pad=24, color=INK)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def ablation(pairs: list[str], out: Path, title: str) -> Path:
    labels, correct, false = [], [], []
    n = None
    for pair in pairs:
        name, _, label = pair.partition("=")
        o = _report(name)["overall"]
        labels.append(label or name)
        correct.append(o["case_ok"]["k"])
        false.append(o["false_answer"]["k"])
        n = o["cases"]
    fig, ax = plt.subplots(figsize=(max(6.0, 1.25 * len(labels) + 1.5), 3.6))
    width = 0.38
    xs = range(len(labels))
    for offset, values, color, name in ((-width / 2, correct, BLUE, "Correct cases"),
                                        (width / 2, false, ORANGE, "False answers")):
        bars = ax.bar([x + offset for x in xs], values, width - 0.04, color=color, label=name)
        for bar, value in zip(bars, values, strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.8, str(value), ha="center",
                    va="bottom", fontsize=9, color=INK)
    ax.set_xticks(list(xs), labels)
    ax.set_ylim(0, n + 6)
    ax.set_ylabel(f"cases (of {n})")
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left", ncol=2)
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def retrieval(dirs: list[Path], out: Path, title: str) -> Path:
    from eval.cases import load_cases
    from eval.metrics import score
    from rag.files import read_jsonl
    rows = []
    for directory in dirs:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        cases = load_cases(ROOT / manifest["cases"])
        for variant, entry in manifest["variants"].items():
            r = score(read_jsonl(ROOT / entry["traces"]), cases)["overall"]["retrieval"]
            rows.append((f"{manifest['id']} {variant}", r["recall@5"], r["n"]))
    rows.sort(key=lambda row: row[1])
    fig, ax = plt.subplots(figsize=(7.2, 0.32 * len(rows) + 1.2))
    bars = ax.barh([r[0] for r in rows], [r[1] for r in rows], 0.7, color=BLUE)
    for bar, (_, value, _) in zip(bars, rows, strict=True):
        ax.text(value + 0.01, bar.get_y() + bar.get_height() / 2, f"{value:.3f}", va="center",
                fontsize=8.5, color=INK)
    ax.set_xlim(0, 1.0)
    ax.set_xlabel(f"Recall@5 (n = {rows[0][2]} dev cases with gold chunks)")
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["heatmap", "ablation", "retrieval"])
    parser.add_argument("items", nargs="+")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--title")
    args = parser.parse_args()
    if args.kind == "heatmap":
        path = heatmap(args.items[0], args.out or FIGURES / f"heatmap_{args.items[0]}.png",
                       args.title)
    elif args.kind == "ablation":
        path = ablation(args.items, args.out or FIGURES / "ablation.png",
                        args.title or "Correct cases and false answers by configuration")
    else:
        path = retrieval([Path(d) for d in args.items], args.out or FIGURES / "retrieval.png",
                         args.title or "Item retrieval on dev")
    print(path)


if __name__ == "__main__":
    main()
