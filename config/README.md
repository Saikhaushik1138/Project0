# Experiment configuration

Generate private keys once with `python -m swarm_security keygen --drones 64`.
The command creates `keys.local.json` with a separate random 32-byte key per
vehicle and refuses to overwrite an existing file. Local keys are Git-ignored.

Run-time configuration is explicit in `python -m swarm_security launch --help`.
Supported profiles are `baseline`, `hmac`, and `chacha20`. Use `--drones` for
sizes from 1 to 64. Each launch records its selected configuration in `runs/`.
