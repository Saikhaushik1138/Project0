# Architecture

The maintained implementation treats payloads as opaque bytes. A future integration may carry a complete serialized MAVLink frame inside the envelope, then validate that frame using a maintained MAVLink library after decryption. It currently parses no flight commands and runs no UDP proxy.

## Envelope version 1

| Field | Bytes | Encoding / purpose |
| --- | ---: | --- |
| Magic | 4 | ASCII `P0SC` |
| Version | 1 | `1` |
| Plaintext length | 2 | Unsigned big-endian integer, maximum 4096 |
| Nonce | 12 | Random bytes from the OS |
| Ciphertext | variable | Encrypted opaque payload |
| Authentication tag | 16 | Poly1305 tag appended by the AEAD library |

Total overhead: 35 bytes. Associated data is the 7-byte header followed by the exact application context. The context is not transmitted; both endpoints must agree on it independently. It should identify the protocol, session, and direction. GPS coordinates are neither a secret key nor proof of location.

`open()` checks bounds and format, authenticates/decrypts, checks the nonce cache, then records the accepted nonce. Invalid packets cannot poison the replay cache. Application code receives plaintext only after authentication succeeds.

## State and lifecycle

Each receiver maintains a FIFO set of the most recent 1024 accepted nonces by default. Memory is bounded; an evicted packet may be accepted again. Restarting the receiver loses the cache. Random nonces make collisions unlikely, not impossible. Establish key-usage limits and a robust session protocol before deployment.

Instances are single-threaded and intended for one peer and direction. There is no peer discovery, key exchange, time synchronization, persistent counter, network transport, command authorization, or lockout mechanism. Authentication proves possession of the shared key, not an individual operator's identity.
