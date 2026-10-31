# Security policy

Project0 is a research implementation of MAVLink transport profiles. The
maintained code is in `swarm_security/`; archived experiments are historical
reference material and are not supported entry points. There is no audited
production release or guaranteed response-time commitment.

## Report a vulnerability

Use this repository's GitHub **Security → Report a vulnerability** option if
private reporting is enabled. If it is unavailable, open an issue requesting a
private reporting channel without posting secrets, sensitive flight logs, or
exploit details. Include the affected commit, expected behavior, reproduction
steps, and the impact once a private channel is available.

For a defect in upstream PX4 itself, consult the preserved [PX4 security policy](docs/px4_security.md)
and the upstream project's current reporting instructions. Project0 does not
provide security support on behalf of PX4.

## Security boundary

The protected profiles authenticate traffic between local relays. They depend
on trusted endpoints, private per-vehicle keys, and the shared host clock.
QGroundControl and PX4 still exchange plaintext with their adjacent relay.
Direct access to PX4's raw UDP port can bypass this research path. Replay state
is held in memory. Read the [architecture and trust boundary](docs/architecture.md)
for the complete scope and assumptions.

Generate keys locally with `python -m swarm_security keygen`; do not commit or
publish them. The default key path is ignored by Git, but custom output paths
must also be kept private. Rotate any credential that has been exposed in
source history, a log, a capture, or a shared artifact.
