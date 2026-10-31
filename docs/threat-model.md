# Threat model and validation

Assume an observer can capture, alter, inject, and replay transport packets, but does not know the shared key. Endpoints and the OS random generator are assumed trustworthy.

| Scenario | Current behavior | Limit |
| --- | --- | --- |
| Payload interception | Payload encrypted using ChaCha20-Poly1305 | Length and traffic patterns remain visible |
| Payload or header alteration | Rejected by format checks or authentication | Does not stop traffic flooding |
| Wrong key / context | Authentication fails | No key distribution implemented |
| Recent replay | Rejected after authentication | Cache eviction and restarts end protection |
| Malformed / oversized data | Rejected before decryption | Network resource limits are not implemented |
| Invalid packet reusing a valid nonce | Does not update replay state | No network rate limiting |
| RF jamming / GPS spoofing | Not addressed | Cryptography does not establish sensor truth or availability |
| Endpoint compromise | Not addressed | Stolen keys permit forgery and decryption |

Automated tests exercise these software behaviors locally. They do not establish performance, operational safety, formal security, or interoperability. Original notes recorded conclusions without reproducible evidence; they remain historical claims, not current validation results.

The archived HMAC script used a public hardcoded key and a truncated token, not authentication over every original frame. The archived ChaCha20 script used a custom nonstandard frame, unauthenticated headers, incorrect command parsing, and replay-state mutation before authentication. Neither should control a vehicle.

See [RFC 8439](https://www.rfc-editor.org/rfc/rfc8439) for the primitive specification and the [cryptography AEAD API](https://cryptography.io/en/latest/hazmat/primitives/aead/) for library guidance.
