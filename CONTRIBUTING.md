# Contributing to Project0

Project0 contains the maintained `swarm_security/` research tools alongside a
PX4 source snapshot. Start with the [setup guide](docs/setup.md) and
[architecture](docs/architecture.md) to understand the project boundary.

## Development workflow

1. Create a descriptive branch from `main`.
2. Create a virtual environment and install with `python -m pip install -e .`.
3. Make one focused change, updating affected documentation and regression tests.
4. Run `scripts/check_project.sh` (or `python -m unittest discover -s tests -v`) and the relevant CLI commands.
5. Open a pull request explaining the problem, resulting behavior, validation, and limitations.

Project tests live in `tests/`; upstream PX4 tests remain in `test/` and
`integrationtests/`. The Python test suite includes local UDP routing checks;
it does not launch Gazebo or control a vehicle. Add a regression test for a
fixed correctness or security defect. Keep deterministic tests independent of
private keys, local build products, and graphical applications.

## Reporting results

For simulation changes, include the relevant run manifest and the validation
performed. State the vehicle count, profile, software revisions, host,
duration, and metric units. Distinguish protocol tests, simulation connectivity,
sustained workloads, and physical flight results. Preserve original research
sources and create new outputs for new measurements.

Never commit credentials, virtual environments, or generated build products.
Review captures and logs before sharing them: telemetry can contain sensitive
locations and identifiers. Report potential vulnerabilities using the
[security policy](SECURITY.md).

## PX4 changes and attribution

Keep PX4 build inputs in their expected locations and preserve upstream notices
and the [license](LICENSE). Avoid unrelated formatting or firmware changes in a
research-tool pull request. The [original PX4 contribution guide](docs/px4_contributing.md)
is preserved for firmware-specific work; upstream PX4 contributions belong in
the upstream project's own review process.
