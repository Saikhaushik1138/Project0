# Changelog

## 0.2.0

- Introduced an installable Python package and offline CLI.
- Added a versioned AEAD envelope with authenticated headers and context.
- Added bounded packet validation and post-authentication replay bookkeeping.
- Added regression tests and Python 3.10–3.13 CI.
- Reorganized original experiments into an explicitly unmaintained archive.
- Rewrote documentation to distinguish demonstrated behavior from future integration work.

### Migration

Original `codes/`, `Solutions/`, and `Vulnerabilities.md` moved under `archive/`. The new package is intentionally not wire-compatible with the original custom proxy format. Use the root README quick start; no network forwarding is enabled.
