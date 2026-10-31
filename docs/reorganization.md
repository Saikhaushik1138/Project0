# File organization and recovery

The PX4 checkout's source layout and existing working changes were preserved.
The original root README is now `docs/px4_upstream_readme.md`. The new root
README describes this research project and links to PX4 information.

| Original | Current location |
| --- | --- |
| `Research paper UAV (2).docx` | `docs/references/research_paper.docx` |
| `Secure internship.pptx` | `docs/references/security_presentation.pptx` |
| Original root Python scripts | `archive/legacy/python/` |
| Original `fly*.sh`, `run_drone.sh`, swarm launcher | `archive/legacy/launchers/` |
| Original `record_*.sh` | `archive/legacy/recording/` |
| `ss/` | `archive/legacy/swarm/` |
| `recordings_<date>/` | `data/recordings/<date>/` |
| Root logs, MAVLink telemetry and parameter files | `data/historical/` |
| Generated in-source CMake files | `archive/reorganization/build-residue.tar.gz` |

The move manifest at `archive/reorganization/manifest.json` records original
paths, destinations, and SHA256 hashes. It also lists removed reproducible Finder
metadata and custom Python bytecode caches. Original scripts and research data
were retained byte-for-byte. Old duplicate launchers are kept only as historical
source; the supported replacements share one implementation.

The generated build archive contains 275 files, including CMake-produced
Makefiles scattered in source folders and root generated configuration files.
These contain paths to an older checkout and do not belong in the source tree.
The working `build/px4_sitl_default` directory was retained. The archive uses
original relative paths, so it can be inspected or extracted into a separate
temporary directory if needed.

`staged-before.patch`, `unstaged-before.patch`, and `git-status-before.txt` capture
the pre-reorganization Git state. The Git index was not reset, restaged, or
committed. Previously staged generated files can therefore appear as staged
additions plus working-tree deletions until the final organization is reviewed
and staged. These are recorded cleanup changes, not lost source code.

New outputs live in Git-ignored `runs/`. Private keys live in Git-ignored
`config/*.local.json`. Do not replace historical recordings with new results.
