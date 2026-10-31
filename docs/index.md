# Project documentation

Start with the [repository overview](../README.md), then choose the guide that
matches your task.

| Task | Guide |
| --- | --- |
| Install Python tools or set up PX4/Gazebo | [Setup and first run](setup.md) |
| Understand sockets, crypto sessions, and the trust boundary | [Architecture](architecture.md) |
| Compare the implemented profiles with the supplied manuscript | [Research scope and evidence](research.md) |
| Inspect recorded test results and simulation limitations | [Validation record](validation.md) |
| Clone pinned submodules and understand what Git contains | [GitHub checkout notes](github.md) |
| Find where original files were moved | [Reorganization record](reorganization.md) |
| Propose a change or reproduce a defect | [Contributing](../CONTRIBUTING.md) |
| Report a potential vulnerability | [Security policy](../SECURITY.md) |

## Source material and evidence

- [Research paper](references/research_paper.docx) and [presentation](references/security_presentation.pptx): original source documents, preserved unchanged.
- [Historical recordings](../data/recordings/): original measurements for independent analysis.
- [Validation artifacts](../data/validation/session-2026-10-31/): retained manifests, logs, metrics, and provenance.
- [Legacy implementations](../archive/legacy/): historical reference code, outside the supported entry points.
- [Earlier GitHub package](../archive/previous-github/): preserved snapshot of the initial research package.

The historical paper and presentation describe a broader research proposal
than the current implementation. Read the research mapping before treating a
reported result as reproduced evidence.

## Upstream PX4 material

The repository includes a PX4 source snapshot. Its [original README](px4_upstream_readme.md),
[contribution guidance](px4_contributing.md), and [security policy](px4_security.md)
are retained for attribution. Project0's root contribution and security files
apply to this repository's maintained research tools. The upstream [license](../LICENSE)
remains at the root.
