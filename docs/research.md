# Research scope and evidence

This project studies security layers around MAVLink communication between PX4
software-in-the-loop vehicles and a ground control station. The supplied
[research paper](references/research_paper.docx) and
[presentation](references/security_presentation.pptx) describe the intended
experiments. Their reported results are retained as historical research claims;
organizing the repository and testing the software does not reproduce those
experiments.

## Security cases

The manuscript's “Evaluated Architectural Parameter Cases” section and slide 9
use four cases. The original shell filenames use a different numbering scheme.
Use the named modes in the current [project guide](../README.md) for new runs.

| Research case | Meaning in the supplied material | Relationship to the current workflow |
| --- | --- | --- |
| Case 1 | Baseline single drone without the added security layer | `baseline` with one vehicle |
| Case 2 | Standard unmodified MAVLink communication across swarm sizes | `baseline` with the selected vehicle count |
| Case 3 | MAVLink plus HMAC for authenticity and integrity | `hmac`; plaintext remains visible on the protected transport |
| Case 4 | MAVLink plus ChaCha20; the paper also describes HMAC authentication | `chacha20`, using ChaCha20-Poly1305 authenticated encryption; this is not an exact reproduction of the manuscript's separately described ChaCha20-plus-HMAC construction |

Slide 6 additionally proposes secondary-token authentication and an affine
cipher derived from latitude and longitude. These proposals are not separate
supported modes. The archived `myenc.py` is a marker-based demonstration, not an
affine cipher or a valid HMAC verifier. The later archived ChaCha20 implementations
contain additional token, GPS, and replay experiments, but their features must
not be inferred from a filename such as “hardened.”

The protected transport terminates at proxies so PX4 and QGroundControl receive
ordinary MAVLink. These modes are custom transport protection, not native
MAVLink 2 message signing. Plaintext remains present at the local endpoints.

## Swarm sizes and experimental procedure

The results section and slides 13–19 cover **1, 4, 8, 16, 32, and 64 vehicles**.
The archived examples also include 2 and 54 vehicles. Those extra examples are
preserved, but they are not additional measurement tiers established by the
presentation. The manuscript's earlier reference to sizes “from 2 to 64” is less
specific than its explicit results list.

The proposed procedure has four stages: initialize PX4 and Gazebo; collect a
clean baseline; apply each disturbance separately; then collect telemetry,
packet captures, and security decisions. Record the mode, vehicle count,
software revisions, host resources, duration, random seed where applicable,
and exact packet counters with every run. Separate startup from steady operation
and repeat comparable runs before drawing performance conclusions.

The sources specify a 4 ms physics step. That setting is not a 4 ms network
delay. Different total simulation durations alone do not measure cryptographic
overhead. A collection of PX4 instances also does not establish an autonomous
formation controller, collision avoidance, peer trust scoring, or swarm-wide
mission control.

## Evidence available in the original files

The nonempty `recordings_20260715_062734/gazebo_stats.log` originally at the
project root records 51.512 seconds of simulated time, 53.339028459 seconds of
real time, 12,878 physics iterations, and a 4 ms step. These agree with the
resource summary on slide 10. The other three `.log` files in the two original
recording directories are empty. A packet capture exists in the earlier
recording directory, but its presence alone does not establish the attack
outcomes in the slides.

No complete per-attempt dataset and reproducible analysis tying all reported
security tables to the delivered implementations was identified during this
review. In particular:

- Slides 13–19 report attack rates for several disturbances, whereas the
  archived Python swarm model selects among only injection, replay, and
  spoofing branches. Some branch outcomes are assigned directly by the model.
- The manuscript reports approximately 99.0–99.8% packet delivery and
  700–980 packets/second. Several presentation rows instead show 97.0–98.8%
  delivery, and their “Throughput/s” values do not specify a numerator unit.
  These series must not be merged without the original measurement method.
- The manuscript's later V12 discussion describes X25519 exchange, signed
  persistent state, and further controls. The delivered files are named V10
  and do not contain that complete V12 implementation.
- Slides 25–26 explicitly retain a one-GCS-to-one-drone routing limitation in
  the historical proxy, despite the separately presented swarm results.

Keep the source documents unchanged for traceability. Generate new result files
from new runs instead of copying presentation percentages into test outputs.

## Metric definitions

Use explicit counters and units. A rejected packet is not automatically a
detected attack: classification requires the known label of that packet or
attempt. Availability failures, authorization failures, and confidentiality
failures need distinct success criteria.

| Metric | Definition | Required interpretation |
| --- | --- | --- |
| ASR | Successful attack attempts / total attack attempts × 100 | Define the objective and what constitutes one attempt before the run |
| ADR | Detected attack attempts / total attack attempts × 100 | Count an attempt once, even if it causes multiple log entries |
| FPR | Legitimate attempts incorrectly classified as attacks / all legitimate attempts × 100 | Distinguish ordinary channel loss from a security classification |
| FNR | Undetected attack attempts / all attack attempts × 100 | This equals 100 − ADR only with the same complete labeling and denominator |
| PDR | Unique legitimate packets delivered / legitimate packets sent × 100 | Exclude duplicates and specify the endpoints and observation window |
| PLR | Legitimate packets not delivered / legitimate packets sent × 100 | This equals 100 − PDR when both use the same packet population |
| Throughput | Successfully delivered bytes or packets / elapsed seconds | Report `bytes/s` or `packets/s`, direction, and whether tunnel overhead is included |
| Real-time factor | Simulated elapsed time / real elapsed time | A simulator timing measure, separate from network throughput |

Report an undefined ratio as unavailable when its denominator is zero. Passive
eavesdropping is generally not detectable merely from packet delivery, so an
ADR/FNR pair for passive observation needs a separate detection mechanism and
clear explanation.

## Limits of the security claims

Authenticated encryption detects changes to protected data. It does not verify
that GPS measurements are physically true, prevent RF interference, or make an
endpoint trustworthy after its key or operating system is compromised. GPS
bound into authenticated data protects the transmitted assertion, not the
sensor that produced it. A plausible movement check is a heuristic.

Per-vehicle credentials can limit cross-vehicle impersonation but cannot identify
an attacker using a still-valid credential for that same vehicle. Revocation,
behavioral detection, routing quarantine, and physical separation are distinct
features and require their own implementation and validation. The supplied
slides discuss these ideas; their discussion is not evidence of a complete
implementation in this repository.

Unique nonces are required for ChaCha20-Poly1305 under a key. Knowing a nonce does
not disclose a secret key or by itself allow keystream computation. Similarly,
a symmetric salt update alone is not evidence of forward secrecy. No
production-security or physical-flight certification follows from the local
software checks.
