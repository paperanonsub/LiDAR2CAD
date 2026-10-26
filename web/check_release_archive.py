"""Test the extracted source archive away from the working source tree.

Creates a fresh temporary directory, verifies archive integrity, runs the
manifest checker, the smoke demo and regression tests with sanitized imports.
Does not push or upload anything. Test dependencies must already be installed.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

WEB = Path(__file__).resolve().parent
RELEASES = WEB / "assets/releases"


def main():
    metadata = json.loads((RELEASES / "release.json").read_text(encoding="utf-8"))
    source = next(item for item in metadata["packages"] if "source" in item["filename"])
    archive_path = RELEASES / source["filename"]
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == source["sha256"]
    with tempfile.TemporaryDirectory(prefix="lidar2cad-release-") as directory:
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.testzip() is None
            for name in archive.namelist():
                assert ".." not in Path(name).parts and not Path(name).is_absolute()
            archive.extractall(directory)
        extracted = Path(directory) / "LiDAR2CAD"
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        # Retain installed dependency locations; this is a source-isolation
        # check, not an assertion of a fresh dependency environment.
        commands = [
            [sys.executable, "-c", "from pathlib import Path; import parking_pipeline, lidar2outline; root=Path.cwd().resolve(); assert Path(parking_pipeline.__file__).resolve().is_relative_to(root); assert Path(lidar2outline.__file__).resolve().is_relative_to(root); print('Imports resolve inside extracted archive')"],
            [sys.executable, "scripts/verify_release.py"],
            [sys.executable, "scripts/run_joint_demo.py"],
            [sys.executable, "-m", "pytest", "tests", "-q"],
            [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--wheel-dir", "checks/wheels"],
        ]
        checks = []
        for command in commands:
            result = subprocess.run(command, cwd=extracted, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(result.stdout[-7000:])
            if result.returncode:
                print(result.stderr[-7000:])
                raise RuntimeError(f"Archive check failed: {' '.join(command[1:])}")
            checks.append({"command": "python " + " ".join(command[1:]), "status": "passed"})
        report = {"source_archive": source["filename"], "archive_sha256": source["sha256"], "extracted_outside_workspace": True,
                  "temporary_test_directory_removed_on_exit": True, "checks": checks, "paper_benchmark_rerun": False}
        (WEB / ".checks").mkdir(exist_ok=True)
        (WEB / ".checks/release-archive-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
