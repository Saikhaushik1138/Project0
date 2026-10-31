# Historical project files

This directory retains the original custom experiments and launchers for
traceability. Their contents are historical implementations, not the supported
way to start the reorganized project. Use the setup and launch instructions in
the [project guide](../README.md).

Some historical scripts start processes immediately, use fixed ports and keys,
or terminate other simulator processes. They have been retained rather than
silently rewritten into apparently validated security implementations. Moving a
file here does not repair its original assumptions or relative paths.

| Directory | Original contents |
| --- | --- |
| `legacy/python/` | ChaCha20 variants, `secure_proxy_v10.py`, `myenc.py`, `hainjec.py`, and `drone_test.py` |
| `legacy/launchers/` | Original single-vehicle, security-case, and Gazebo launch shell scripts |
| `legacy/recording/` | Original recording shell scripts |
| `legacy/swarm/` | The original `ss/` Python model and size-specific wrappers |

## Historical case names

| Original entry point | Behavior in the original file |
| --- | --- |
| `fly_case0.sh`, `fly_case4.sh`, `fly_case5.sh` | Similar launchers for `Chacha20_hardened.py`; reference a missing `record_chacha20_hardened.sh` |
| `fly_case1.sh` | Standard PX4/Gazebo baseline |
| `fly_case2.sh` | Standard PX4/Gazebo with instructions for a separate injection demonstration |
| `fly_case3.sh` | Starts the `myenc.py` demonstration |
| `fly_case6.sh` | Starts `secure_proxy_v10.py` with fixed development credentials |
| `launch_swarm_gazebo.sh` and `fly_swarm_*.sh` | Start PX4/Gazebo instances; do not attach the security layers by themselves |
| `swarm_*.py` | Run an in-process Python model, independent of PX4, Gazebo, and QGroundControl |

The paper's four architectural cases use different numbering. See
[research scope and evidence](../docs/research.md) before comparing old results
or choosing a new experimental mode.

## Known limitations found during organization

- `myenc.py` performs unused HMAC work and accepts a literal `SIGNED_OK` suffix.
  That suffix is not a cryptographic signature or proof of authorization.
- `secure_proxy_v10.py` falls back to fixed credentials and prints keys. Its
  bridge calls the lower-level decryption routine directly, bypassing additional
  replay, sequence, rate, and command checks in `process_packet`.
- The V10 subkey state uses locally generated salts without a peer exchange,
  and advances its counter during encryption and decryption. This is not a
  complete interoperable key-rotation protocol. A shared Python process can
  hide synchronization problems that separate endpoints would encounter.
- The original launchers contain working-directory assumptions, fixed UDP
  endpoints, broad process termination, and references to missing scripts.
  Several use external tools whose presence is assumed rather than checked.
- The original Python swarm model assigns several attack outcomes by branch
  instead of sending those packets through the receiver's verification path.
  Its printed metrics therefore are not an integration test of the archived
  proxies. Its shared development credentials also do not model per-vehicle
  credential isolation.
- That model labels command 22 as disarm. MAVLink command 22 is takeoff;
  arm/disarm uses `MAV_CMD_COMPONENT_ARM_DISARM` (400), with the action in its
  parameter. Do not use the historical labels as a command reference.
- A one-node run of the original model can wait indefinitely while choosing a
  different receiving node. The original size-specific wrappers also contain
  narrative conclusions that do not constitute measured flight results.

The report, presentation, original logs, and captures remain research records.
Their historical figures have not been re-certified by the repository cleanup.
