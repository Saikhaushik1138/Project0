# Security

Project0 is a research prototype, not an audited or flight-ready system. Only `src/project0/` is maintained; archived scripts are historical artifacts with known defects.

Report potential vulnerabilities through GitHub private vulnerability reporting if the repository owner has enabled it. Otherwise open an issue requesting a private contact without including secrets or exploit-sensitive details. Do not post live keys or identifying flight logs.

Keys must be generated randomly and provisioned through a trusted channel. Environment variables are a development convenience, not a complete secret-management system. Rotate any key ever committed to repository history. Production use requires authenticated sessions, key rotation, restart-safe replay protection, authorization, resource limits, interoperability testing, and independent review.
