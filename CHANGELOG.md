# Changelog

## 0.3.0

- Package the current `swarm_security` tools with an installable `swarm-security` command.
- Provide portable onboarding, a documentation index, and project-specific contribution and security guidance.
- Expand CI across Python 3.10–3.13, including installation, regression tests, distribution builds, and a 64-vehicle dry run.
- Update issue and pull-request templates for research software and simulation reports.
- Reject malformed heartbeat status safely during startup instead of crashing or accepting invalid vehicle IDs.
- Reject non-finite replay ages and invalid session capacities before creating a codec.
- Add CLI regression coverage for help, version reporting, private key creation, and refusal to overwrite credentials.

The original research materials and validation evidence remain under their existing paths. This release does not claim a new flight or Gazebo performance measurement.
