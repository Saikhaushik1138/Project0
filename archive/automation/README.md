# Preserved GitHub automation

The files in `github-workflows/` are the repository's previous PX4 and Gemini
workflow definitions. They were moved here byte-for-byte before publishing the
organized project. `manifest.json` records their original locations and SHA256
checksums.

Files outside `.github/workflows/` are inactive. This preserves the originals
without enabling PX4-specific deployment jobs, hourly Gemini issue triage,
automated issue comments, or external service calls in this personal project.
No archived workflow was executed as part of the upload preparation.

The project-specific `swarm-tests.yml` remains active in `.github/workflows/`.
It runs the Python test suite with read-only repository permissions.

To restore an archived workflow, first review its triggers, permissions,
repository assumptions, service destinations, and required secrets. Then copy
only the chosen file back to `.github/workflows/`. The upstream metadata jobs
target PX4's S3 bucket, while the Gemini jobs require their own service setup.
The archived Gemini workflows can reference one another and the retained
`.github/commands/` files.
