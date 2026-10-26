"""Curate local implementation and reported data; never publish or modify inputs.

Run from the workspace root: python TII/web/build_release.py
No model weights, raw field geometry, private logs, or third-party code are copied.
"""
from __future__ import annotations

import ast
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

WEB = Path(__file__).resolve().parent
TII = WEB.parent
ROOT = TII.parent
RELEASE = TII / "opensource"
DOWNLOADS = WEB / "assets/releases"
PROVENANCE = {}
DENIED_PARTS = {"__pycache__", ".pytest_cache", ".git", ".venv", "outputs", "checks", "dist"}


def sha256(path):
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_source(source, target, portable_test=False):
    destination = RELEASE / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    if portable_test:
        text = source.read_text(encoding="utf-8-sig")
        text = re.sub(r"^ROOT = Path\(__file__\)\.resolve\(\)\.parents\[3\]\r?\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^sys\.path\.insert\(0, str\(ROOT\)\)\r?\n", "", text, flags=re.MULTILINE)
        destination.write_text(text, encoding="utf-8")
    else:
        shutil.copyfile(source, destination)
    PROVENANCE[target] = {"origin": source.relative_to(ROOT).as_posix(), "source_sha256": sha256(source),
                          "packaging_change": "Removed research-root sys.path injection from standalone tests" if portable_test else "none"}


def build_sources():
    snapshot = TII / "deliverables/LiDAR2CAD_core_algorithm_20261021"
    for package in ("lidar2outline", "parking_pipeline"):
        # Preserve the internally consistent extraction snapshot and add the
        # self-contained joint/design modules absent from that snapshot.
        for source in sorted((snapshot / package).glob("*.py")):
            copy_source(source, f"{package}/{source.name}")
        for source in sorted((ROOT / package).glob("*.py")):
            if not (snapshot / package / source.name).is_file():
                copy_source(source, f"{package}/{source.name}")
    copy_source(snapshot / "configs/R309_portable.yaml", "configs/R309_portable.yaml")
    for source in sorted((snapshot / "tests").glob("test_*.py")):
        copy_source(source, f"tests/{source.name}")
    copy_source(TII / "code/tests/test_joint_reconstruction_v3.py", "tests/test_joint_reconstruction_v3.py", portable_test=True)
    copy_source(ROOT / "tests/test_design_assisted_r309.py", "tests/test_design_assisted_r309.py")


def build_data():
    reported = RELEASE / "data/reported_results"
    copy_source(TII / "results/author_results_20261025/author_results.json", "data/reported_results/author_results.json")
    original = json.loads((reported / "author_results.json").read_text(encoding="utf-8"))
    for number, table in enumerate(original["tables"], 1):
        target = reported / f"table_{number:02d}.csv"
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(table["headers"])
            writer.writerows(table["rows"])
        PROVENANCE[target.relative_to(RELEASE).as_posix()] = {"origin": "TII/results/author_results_20261025/author_results.json",
            "packaging_change": f"Lossless CSV extraction of source table {number}; values not recomputed"}
    for folder in ("external_20261025", "standalone_20261025"):
        for source in sorted((TII / "paper/final_en/tables" / folder).glob("*.tex")):
            copy_source(source, f"data/reported_results/manuscript_tables/{folder}/{source.name}")
    write_json(reported / "provenance.json", {
        "type": "reported_aggregate_results_not_raw_benchmark",
        "table_count": len(original["tables"]),
        "locally_rerun": False, "independent_audit": "not_performed",
        "source": "author_results.json",
        "semantic_frontend_weights_included": False,
        "exact_experiment_source_snapshot_available": False,
        "warning": "Local implementation and historical local data are not certified to reproduce these off-machine results.",
    })
    # A deterministic artificial scene mirrors the behavioral test, not field observations.
    points = [[round(index * .025, 5), 0., z] for index in range(161) for z in (.5, .7, 1., 1.2)]
    walls = []
    for name, lower, upper in (("A", 0., 1.5), ("B", 2.1, 4.)):
        rows = [index for index, point in enumerate(points) if lower <= point[0] <= upper]
        walls.append({"wall_id": name, "coordinates": [[lower, .015], [upper, .015]], "source_voxel_rows": rows,
                      "observed_support_fraction": 1., "source": "synthetic_fixture", "status": "observed"})
    write_json(RELEASE / "data/synthetic_demo/input.json", {
        "is_synthetic": True, "purpose": "Smoke test only; never used for manuscript scores", "units": "metres",
        "points": points, "walls": walls, "design_segments": [{"design_segment_id": "D-S", "design_wall_id": "D", "coordinates": [[0., .18], [4., .18]]}],
        "design_openings": [], "config_overrides": {},
    })
    fields = []
    for folder in ("icpar", "quzhou_b01", "quzhou_b02", "semantic_cache", "semantic_models"):
        for path in sorted((TII / "data" / folder).glob("*")):
            if path.is_file():
                fields.append({"workspace_relative_path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                    "local_available": True, "public_archive_included": False,
                    "reason": "Redistribution permissions not established; not certified as matching current off-machine results"})
    write_json(RELEASE / "data/DATA_INVENTORY.json", {
        "schema": "lidar2cad-public-data-inventory/v1", "date": "2026-10-26", "field_inputs": fields,
        "excluded_categories": ["raw scans and engineering drawings", "historical reference geometry", "model weights and cached features", "third-party model source"],
        "missing_current_run_artifacts": ["exact off-machine source snapshot", "matched raw prediction geometry and logs", "version-matched reference geometry and relation labels", "hardware specification"],
        "included_data": ["reported aggregate tables and provenance", "explicitly synthetic demo inputs"],
        "complete_field_benchmark_release": False,
    })


def eligible_files():
    return [p for p in sorted(RELEASE.rglob("*")) if p.is_file() and not any(part in DENIED_PARTS for part in p.relative_to(RELEASE).parts) and p.suffix not in {".pyc", ".pyo"}]


def manifest():
    files = []
    for path in eligible_files():
        name = path.relative_to(RELEASE).as_posix()
        if name == "SOURCE_MANIFEST.json":
            continue
        if path.suffix == ".py":
            content = path.read_text(encoding="utf-8-sig")
            ast.parse(content, filename=name)
        if path.suffix in {".py", ".json", ".yaml", ".md", ".toml"} or path.name == "LICENSE":
            content = path.read_text(encoding="utf-8-sig")
            for pattern in (r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", r"gh[pousr]_[A-Za-z0-9]{30,}", r"AKIA[A-Z0-9]{16}", r"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"):
                if re.search(pattern, content):
                    raise ValueError(f"Possible credential in {name}; not packaging")
        files.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256(path), **PROVENANCE.get(name, {"origin": "release preparation", "packaging_change": "new release documentation, configuration, or fixture"})})
    write_json(RELEASE / "SOURCE_MANIFEST.json", {"schema": "lidar2cad-source-release/v1", "date": "2026-10-26",
        "code_license": "MIT", "released_data_license": "CC-BY-4.0",
        "source_snapshot": "Local implementation, 2026-10-26; not certified as matching off-machine paper runs",
        "publication_status": "prepared_locally_not_uploaded", "files": files})
    return files


def make_archive(filename, files):
    destination = DOWNLOADS / filename
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(set(files)):
            name = "LiDAR2CAD/" + path.relative_to(RELEASE).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 26, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert all(not p.startswith(("/", "\\")) and ".." not in Path(p).parts for p in archive.namelist())
    return {"filename": filename, "url": "assets/releases/" + filename, "bytes": destination.stat().st_size, "sha256": sha256(destination), "files": len(files)}


def main():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    build_sources()
    build_data()
    files = manifest()
    all_paths = eligible_files()
    data_files = [p for p in all_paths if p.relative_to(RELEASE).parts[0] in {"data", "docs"} or p.name in {"README.md", "LICENSE", "LICENSE-DATA.md", "THIRD_PARTY_NOTICES.md"}]
    # The data archive has no source manifest claiming files outside its scope.
    code_files = [p for p in all_paths if p.relative_to(RELEASE).parts[0] != "data"]
    # Include small data so the source archive's quick-start actually works.
    code_files += [p for p in all_paths if p.relative_to(RELEASE).parts[0] == "data"]
    packages = [make_archive("LiDAR2CAD-source-v0.1.0.zip", code_files), make_archive("LiDAR2CAD-data-v0.1.0.zip", data_files)]
    write_json(DOWNLOADS / "release.json", {"project": "LiDAR2CAD", "version": "0.1.0", "date": "2026-10-26",
        "remote_repository": None, "publication_status": "local_downloads_prepared_not_hosted",
        "code_license": "MIT", "data_license": "CC-BY-4.0", "complete_field_benchmark": False,
        "packages": packages, "limitations": ["Raw field scans and drawings excluded", "Headline experiment not independently rerun", "Matching off-machine source/predictions/references absent"]})
    sums = "\n".join(item["sha256"] + "  " + item["filename"] for item in packages) + "\n"
    (DOWNLOADS / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")
    shutil.copyfile(RELEASE / "data/DATA_INVENTORY.json", DOWNLOADS / "data-inventory.json")
    shutil.copyfile(RELEASE / "docs/REPRODUCIBILITY.md", DOWNLOADS / "REPRODUCIBILITY.md")
    print(json.dumps({"source_files": len(files), "reported_tables": len(json.loads((RELEASE / 'data/reported_results/author_results.json').read_text(encoding='utf-8'))['tables']), "packages": packages}, indent=2))


if __name__ == "__main__":
    main()
