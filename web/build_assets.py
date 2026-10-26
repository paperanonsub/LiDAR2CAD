"""Export original manuscript figures for the static homepage without changing sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import fitz
from PIL import Image

WEB = Path(__file__).resolve().parent
PAPER = WEB.parent / "paper" / "final_en"
ASSETS = WEB / "assets"
FIGURES = [
    ("full_rewrite_20261024/fig1_architecture.pdf", "architecture.webp", 2400),
    ("full_rewrite_20261024/fig2_stages.pdf", "stages.webp", 2400),
    ("full_rewrite_20261024/fig3_external_global.pdf", "global-comparison.webp", 2400),
    ("standalone_20261025/fig6_sensitivity_topology_a.pdf", "sensitivity-shift.webp", 1400),
    ("standalone_20261025/fig6_sensitivity_topology_b.pdf", "sensitivity-deletion.webp", 1400),
    ("standalone_20261025/fig7_sources_quality_a.pdf", "provenance.webp", 1400),
]
for region in range(1, 5):
    for stage in range(1, 5):
        FIGURES.append((f"standalone_20261025/fig5_roi{region}_stage{stage}.pdf", f"roi-{region}-stage-{stage}.webp", 1000))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    sources = []
    for source_name, output_name, target_width in FIGURES:
        source = PAPER / "figures" / source_name
        destination = ASSETS / output_name
        with fitz.open(source) as document:
            page = document[0]
            scale = target_width / page.rect.width
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            picture = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            picture.save(destination, "WEBP", quality=94, method=6)
        sources.append({"asset": f"assets/{output_name}", "source": source.relative_to(WEB.parent).as_posix(), "source_sha256": sha256(source), "width": picture.width, "height": picture.height, "bytes": destination.stat().st_size})
        print(f"{output_name}: {picture.width}x{picture.height}, {destination.stat().st_size:,} bytes")
    paper_source = PAPER / "main_en.pdf"
    paper_target = ASSETS / "LiDAR2CAD-paper.pdf"
    shutil.copyfile(paper_source, paper_target)
    with fitz.open(paper_target) as document:
        page_count = len(document)
    sources.append({"asset": "assets/LiDAR2CAD-paper.pdf", "source": "paper/final_en/main_en.pdf", "source_sha256": sha256(paper_source), "pages": page_count, "bytes": paper_target.stat().st_size})
    manifest = {"project": "LiDAR2CAD", "description": "Static homepage assets exported from the current manuscript; original PDF sources are unchanged.", "results_source": "results/author_results_20261025/author_results.json", "evidence_note": "Author-confirmed off-machine measurements; not independently rerun for this website.", "assets": sources}
    (ASSETS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Paper copied unchanged: {page_count} pages, {paper_target.stat().st_size:,} bytes")
    print(f"Exported {len(FIGURES)} figures. Total assets: {sum(item['bytes'] for item in sources):,} bytes")


if __name__ == "__main__":
    main()
