"""Export aligned full-scene comparisons from immutable manuscript inputs.

This display-only adapter never fits, shifts, repairs, or evaluates geometry.
All writes are restricted to web/assets/compare-*.webp and its manifest.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import fitz
from PIL import Image, ImageOps
from shapely.geometry import LineString
import ezdxf

WEB = Path(__file__).resolve().parent
ROOT = WEB.parents[1]
ASSETS = WEB / "assets"
FROZEN = ROOT / "TII/results/full_rewrite_20261024/views"
SIDE = ROOT / "TII/paper/figures/prior_completion_v4/fig2_design_display_sources.geojson"
STATE = ROOT / "TII/results/independent_validation/region_truth_v3/joint_reconstruction_v4/joint_scene_state.json"
POINTS = ROOT / "TII/data/semantic_cache/exact_voxels.npz"
ARCH = ROOT / "outputs/parking/design_fusion/icpar_r309_aligned/artifacts/design_arch.json"
DESIGN_AUDIT = ROOT / "TII/paper/figures/full_rewrite_20261024/fig3a_cad_overlay.json"
DESIGN_ANNOTATED = ROOT / "TII/paper/figures/设计稿带标注.pdf"
COMPLETE_ANNOTATED = ROOT / "TII/paper/figures/最终稿带标注.pdf"
EXTENT = (-3.7, 298.8, -1.8, 246.9)
WIDTH, HEIGHT, DPI = 1800, 1480, 180


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_record(path):
    try:
        name = path.relative_to(ROOT).as_posix()
    except ValueError:
        name = path.name  # Do not publish personal absolute paths.
    return {"source": name, "sha256": sha(path)}


def groups_from_sidecar():
    side = read(SIDE)
    groups, seen = {}, set()
    for feature in side["features"]:
        category = feature["properties"]["category"]
        xy = np.round(feature["geometry"]["coordinates"], 6)
        key = (category, LineString(xy).normalize().wkb)
        if key not in seen:
            groups.setdefault(category, []).append(xy)
            seen.add(key)
    assert {key: len(lines) for key, lines in groups.items()} == side["display_path_counts"]
    return groups


def design_paths():
    # Read the original design at its archived initial registration. Do not
    # call load_cad_overlay(), which would also rewrite its manuscript audit.
    sys.path.insert(0, str(ROOT / "TII/experiments"))
    from paper_full_map_design_layers import entity_paths
    arch, audit = read(ARCH), read(DESIGN_AUDIT)
    source = Path(arch["source_dxf"])
    assert sha(source) == audit["source_sha256"]
    assert sha(ARCH) == audit["structural_extraction_sha256"]
    transform = np.asarray(arch["transform_2d_mm_to_lidar_m"])
    np.testing.assert_array_equal(transform, audit["transform_2d_mm_to_lidar_m"])
    result, seen = [], set()

    def add(category, raw):
        raw = np.asarray(raw, dtype=float)[:, :2]
        if len(raw) < 2:
            return
        xy = raw @ transform[:2, :2].T + transform[:2, 2]
        line = LineString(xy)
        if line.length <= 1e-8:
            return
        key = (category, LineString(np.round(xy, 6)).normalize().wkb)
        if key not in seen:
            result.append((category, xy))
            seen.add(key)

    for category, field, items in (("wall", "pts", arch["walls"]), ("column", "ring", arch["columns"]), ("opening", "pts", arch["openings"])):
        for item in items:
            raw = np.asarray(item[field], dtype=float)
            if (category == "column" or item.get("closed", False)) and not np.array_equal(raw[0], raw[-1]):
                raw = np.vstack([raw, raw[0]])
            add(category, raw)
    facilities = {"04.标准车位", "04.微型车位", "残疾人车位", "无障碍车", "1.2障碍车", "车道中线", "车道边线"}
    for entity in ezdxf.readfile(source).modelspace():
        if entity.dxf.layer not in facilities and "箭头" not in entity.dxf.layer:
            continue
        for outline in entity_paths(entity):
            add("facility", [(p.x, p.y) for p in outline.flattening(distance=20.0)])
    assert dict(Counter(category for category, _ in result)) == audit["path_counts"]
    return result, source


def lines(ax, coords, color="white", width=.65):
    if len(coords):
        ax.add_collection(LineCollection(coords, colors=color, linewidths=width))


def canvas():
    # Matplotlib truncates fractional pixel sizes; offset the floating-point
    # boundary by 0.01 pixels so the exported integer dimensions stay exact.
    fig = plt.figure(figsize=((WIDTH + .01) / DPI, (HEIGHT + .01) / DPI), dpi=DPI, facecolor="black")
    ax = fig.add_axes([0, 0, 1, 1], facecolor="black")
    ax.set_xlim(EXTENT[:2])
    ax.set_ylim(EXTENT[2:])
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    return fig, ax


def save_picture(picture, name, inputs, counts):
    destination = ASSETS / f"compare-{name}.webp"
    assert picture.size == (WIDTH, HEIGHT)
    picture.save(destination, "WEBP", quality=94, method=6)
    print(f"{destination.name}: {WIDTH}x{HEIGHT}, {destination.stat().st_size:,} bytes", flush=True)
    return {"asset": "assets/" + destination.name, "width": WIDTH, "height": HEIGHT,
            "sha256": sha(destination), "bytes": destination.stat().st_size,
            "inputs": [source_record(path) for path in inputs], "display_counts": counts}


def save(fig, ax, name, inputs, counts):
    x0, x1, y0, y1 = EXTENT
    x, y = x0 + (x1 - x0) * .055, y0 + (y1 - y0) * .055
    ax.plot([x, x + 50], [y, y], color="white", linewidth=1.5, zorder=10)
    ax.text(x + 25, y + 5, "50 m", ha="center", color="white", fontsize=10,
            bbox={"facecolor": "black", "edgecolor": "none", "pad": 1}, zorder=11)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=DPI, facecolor="black")
    plt.close(fig)
    buffer.seek(0)
    return save_picture(Image.open(buffer).convert("RGB"), name, inputs, counts)


def annotated_picture(source):
    """Rasterize an author's circled PDF without redrawing its annotations."""
    with fitz.open(source) as document:
        page = document[0]
        scale = WIDTH / page.rect.width
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        picture = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    # Remove the thin white Acrobat page edge, then fit to the comparison canvas.
    picture = picture.crop((2, 2, picture.width - 2, picture.height - 2))
    picture = ImageOps.fit(picture, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    picture.paste("black", (0, 0, WIDTH, 2))
    picture.paste("black", (0, HEIGHT - 2, WIDTH, HEIGHT))
    picture.paste("black", (0, 0, 2, HEIGHT))
    picture.paste("black", (WIDTH - 2, 0, WIDTH, HEIGHT))
    return picture


def main():
    ASSETS.mkdir(exist_ok=True)
    protected = [SIDE, STATE, POINTS, ARCH, DESIGN_AUDIT, DESIGN_ANNOTATED, COMPLETE_ANNOTATED]
    before = {path: sha(path) for path in protected}
    exports = []
    groups = groups_from_sidecar()
    full = read(FROZEN / "full.json")
    state = read(STATE)
    walls = [obj["current_geometry"] for obj in state["objects"].values()
             if obj["kind"] in {"WALL_FACE_TRACE", "INFERRED_WALL_FACE", "PRIOR_INFERRED_WALL_FACE"}]
    walls += groups["cad_unverified_wall"]
    facilities = sum((groups.get(key, []) for key in ("parking_stall", "accessible_aisle", "lane_centre", "direction_arrow", "lane_edge")), [])
    fig, ax = canvas()
    lines(ax, facilities, "#78958A", .35)
    lines(ax, walls)
    lines(ax, full["columns"], "#C7A0FF", .7)
    complete_counts = {"wall_paths": len(walls), "column_paths": len(full["columns"]), "facility_paths": len(facilities)}
    exports.append(save(fig, ax, "complete", [STATE, SIDE, FROZEN / "full.json"], complete_counts))
    exports.append(save_picture(annotated_picture(COMPLETE_ANNOTATED), "complete-annotated",
                                [COMPLETE_ANNOTATED], complete_counts))
    with np.load(POINTS) as archive:
        points = archive["centroids"][:, :2]
    x0, x1, y0, y1 = EXTENT
    points = points[(points[:, 0] >= x0) & (points[:, 0] <= x1) & (points[:, 1] >= y0) & (points[:, 1] <= y1)]
    count = len(points)
    stride = max(1, len(points) // 150000) if len(points) > 150000 else 1
    points = points[::stride]
    fig, ax = canvas()
    ax.scatter(points[:, 0], points[:, 1], s=.22, c="#B5BEC9", linewidths=0)
    exports.append(save(fig, ax, "cloud", [POINTS], {"source_points_in_view": count, "displayed_points": len(points), "display_stride": stride}))
    paths, source_dxf = design_paths()
    exports.append(save_picture(annotated_picture(DESIGN_ANNOTATED), "design",
                                [DESIGN_ANNOTATED, ARCH, DESIGN_AUDIT, source_dxf],
                                dict(Counter(category for category, _ in paths))))
    names = {"lidar": "lidar_only", "hough": "probabilistic_hough", "contour": "dp_contour",
             "ransac": "ransac_lines", "skeleton": "morph_skeleton", "lsd": "lsd", "fld": "fld", "edlines": "edlines"}
    for key, frozen_name in names.items():
        folder = ROOT / "TII/results/fig4_external_expansion_20261024/views" if key in {"fld", "edlines"} else FROZEN
        source = folder / f"{frozen_name}.json"
        view = read(source)
        fig, ax = canvas()
        lines(ax, view["walls"])
        lines(ax, view["columns"], "#C7A0FF", .7)
        exports.append(save(fig, ax, key, [source], {"wall_paths": len(view["walls"]), "column_paths": len(view["columns"])}))
    assert all(sha(path) == value for path, value in before.items()), "An immutable source changed"
    manifest = {"project": "LiDAR2CAD", "coordinate_extent_xyxy": list(EXTENT),
                "dimensions": [WIDTH, HEIGHT], "policy": "Display only; identical map extent, aspect ratio, scale bar and raster dimensions. The design comparison uses author-supplied red circle annotations on both the design and corresponding complete-reconstruction views. Frozen geometry unchanged. No fitting, shifts, synthetic perturbations or new experiments.",
                "design_stage": "Author-annotated original design at archived initial registration, not locally corrected.",
                "cloud_display": "Source voxel centroids, top-down XY projection; deterministic striding matches the manuscript cloud display policy.",
                "complete_display": "Manuscript complete reconstruction, including observed/inferred walls, unverified retained design, columns and mapped facilities. The Design CAD pair uses the author-annotated complete-reconstruction PDF. Display provenance does not imply field verification.",
                "evaluation_scope": "Qualitative full-scene comparison; quantitative metrics remain restricted to annotated evaluation regions.",
                "assets": exports}
    (ASSETS / "comparison-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(exports)} aligned comparison views; protected inputs unchanged.")


if __name__ == "__main__":
    main()
