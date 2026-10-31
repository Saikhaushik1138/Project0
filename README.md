# Project0 · UAV Communication Security Lab

**A reproducible research foundation for exploring authenticated encryption around UAV telemetry.**

[![Python checks](https://github.com/Saikhaushik1138/Project0/actions/workflows/ci.yml/badge.svg)](https://github.com/Saikhaushik1138/Project0/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Status: research prototype](https://img.shields.io/badge/status-research_prototype-amber)

Project0 began as an internship study of MAVLink communication security. This repository now separates its original experiments from a small, testable Python implementation of ChaCha20-Poly1305 authenticated encryption.

> **Scope:** an offline educational prototype, not a flight-ready security gateway. The custom envelope is not MAVLink-compatible. No PX4, Gazebo, or QGroundControl integration is claimed or tested.

## What is included

- A versioned binary envelope with encrypted payloads and authenticated headers/context.
- Strict key, packet-size, and format validation.
- Bounded replay detection updated only after successful authentication.
- An offline CLI demo, regression tests, and a Python-version CI matrix.
- Original research notes and scripts preserved under [`archive/`](archive/README.md).

## Quick start

Requires Python 3.10 or later. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
export DRONE_CHACHA_KEY="$(project0 keygen)"
project0 demo
python -m unittest discover -s tests -v
```

For PowerShell, set the key with `$env:DRONE_CHACHA_KEY = project0 keygen`.
The key generator prints a fresh secret: keep it private and never commit it.
The demo prints three PASS messages for round-trip recovery, tamper rejection, and replay rejection. It opens no network connections.

## Use the Python API

```python
from project0 import SecureChannel, load_key

key = load_key()
context = b"lab/session-1/gcs-to-uav"
sender = SecureChannel(key, context=context)
receiver = SecureChannel(key, context=context)
packet = sender.seal(b"example telemetry")
assert receiver.open(packet) == b"example telemetry"
```

The sender and receiver must share the key and exact context. A real duplex design needs distinct directional keys and authenticated session establishment; the example does not implement either.

## Research context

MAVLink 2 supports optional message signing for authentication, but does not provide encryption. See the official [signing guide](https://mavlink.io/en/guide/message_signing.html) and [security FAQ](https://mavlink.io/en/about/faq.html). Project0 explores an external encryption layer; it does not replace a MAVLink parser or its signing implementation.

| Approach studied | Role | Important limitation |
| --- | --- | --- |
| Operator 2FA | Operator authentication | Does not itself protect telemetry |
| Affine cipher | Historical teaching exercise | Not suitable for modern confidentiality |
| HMAC-SHA-256 | Integrity and shared-key authentication | Does not encrypt messages |
| ChaCha20-Poly1305 | Authenticated encryption | Requires sound key, nonce, and session management |

## Repository guide

| Location | Contents |
| --- | --- |
| `src/project0/` | Maintained envelope implementation and CLI |
| `tests/` | Automated security-behavior regression tests |
| [Architecture](docs/architecture.md) | Wire format and integration boundaries |
| [Threat model](docs/threat-model.md) | Guarantees, limitations, and validation scope |
| `archive/` | Unverified historical experiments and notes |
| [Contributing](CONTRIBUTING.md) | Development and review workflow |
| [Security](SECURITY.md) | Reporting guidance and deployment limitations |

## Next milestones

- Establish authenticated sessions and directional key derivation.
- Persist replay state or rotate session keys safely across restarts.
- Integrate a maintained MAVLink parser and validate complete frames in SITL.
- Measure bandwidth, latency, packet loss, and CPU overhead reproducibly.
- Obtain independent security review before considering real hardware.

No benchmark or flight-test results are claimed. No license is currently granted; the repository owner should select a license before redistribution.
