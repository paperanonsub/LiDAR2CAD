# Reproducibility boundaries

## Current reported results

The current manuscript uses author_results_20261025/author_results.json,
imported from an author-supplied results document. Its metadata explicitly
states that measurements were completed on another computer, were not
locally rerun, and were not independently audited. The original JSON is
preserved, including those limitations. CSV conversion is lossless: source
headers and cells are retained without normalizing or recomputing scores.

## Available implementation

This release preserves the internally consistent 2026-10-21 extraction
snapshot and adds the joint/design modules absent from it from the local
2026-10-26 working tree. Exact origins and hashes are in SOURCE_MANIFEST.json.
Unit tests exercise source ownership, gap support, opening vetoes, scene
validation, and exports. Tests use synthetic fixtures and cannot establish
the manuscript's scene-level accuracy or runtime on unknown hardware.

## What is missing for exact headline-result reproduction?

1. The exact off-machine implementation commit or archived source snapshot.
2. Identically registered design inputs and field observations for those runs.
3. Version-matched evaluation geometry and relation annotations.
4. Per-method predictions, evaluation commands, and execution logs.
5. Semantic checkpoints/features with redistribution permissions.
6. The hardware specification and environment lock for the timing experiment.

Historical inputs and references elsewhere in the research workspace must
not fill these gaps silently. The supplied facilities A/B/C identifiers are
preserved; no invented mappings to local sites are added.

## Release checks versus experiment verification

The release checker validates package consistency and provenance. The
synthetic demo verifies that the API runs and exports coherent artifacts.
Neither is an independent experiment-integrity audit or field-data benchmark.
