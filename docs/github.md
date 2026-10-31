# GitHub checkout and upload contents

This snapshot includes the organized UAV project, the PX4 source tree, original
research documents, historical recordings, legacy scripts, and validation
evidence. It extends the existing `Saikhaushik1138/Project0` history. The earlier
GitHub package is retained under `archive/previous-github/`, with its original
commit and file hashes in `SNAPSHOT.json`.

Clone with PX4's pinned submodules:

```bash
git clone --recurse-submodules https://github.com/Saikhaushik1138/Project0.git
cd Project0
git fetch --tags
```

Follow [setup](setup.md) to create the Python environment and build PX4 for your
machine. The PX4 source snapshot is based on upstream commit
`99c40407ffd7ac184e2d7b4b293f36f10fe561ef` with the project's existing local
changes. The upload retains the project's history rather than importing all
upstream PX4 development history. The vendor tag `v1.15.4-0.1.0` supplies the
version format required by PX4's build metadata generator; it is this project's
snapshot tag, not an upstream PX4 release.

Submodule references preserve their exact upstream revisions. The local NuttX
apps deletion is retained as a patch in
`archive/reorganization/submodule-changes/`, with application instructions.

Private keys, Python environments, PX4 build products, caches, and generated
simulator state stay local. They are reproducible or machine-specific and are
not source files. Generate fresh keys after cloning. Meaningful JSON, logs,
and ULog evidence from the validation runs is preserved under
`data/validation/session-2026-10-31/`.

Only `.github/workflows/swarm-tests.yml` is active. The previous upstream PX4
deployment and Gemini automation definitions are preserved under
`archive/automation/`; uploading this project does not enable those external
publishing or messaging workflows.
