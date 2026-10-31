# Retained validation evidence

This directory contains byte-for-byte copies of the useful outputs from the
31 October 2026 validation session. Its layout preserves paths relative to the
original local `runs/` directory. `evidence-manifest.json` records original
paths, repository destinations, sizes, and SHA256 checksums.

The evidence includes the protocol benchmark, smoke-test summaries and launcher
logs, experiment manifests, relay counters and status, Gazebo logs, PX4 logs,
and vehicle ULog files. The failed initial smoke run is retained alongside the
corrected successful runs. Consult [the validation report](../../../docs/validation.md)
for interpretation and testing limits.

Generated ROMFS copies, executable symlinks, `dataman`, parameter state, lock
files, private keys, and caches were excluded. These are machine runtime state,
not required measurement evidence. Original local files remain under `runs/`.

Absolute paths, process IDs, and working-directory references inside the copied
logs and manifests describe the original run; they are evidence records, not
commands or portable runtime configuration.
