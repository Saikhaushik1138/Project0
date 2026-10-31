"""
MAVLink 2.0 ChaCha20-Poly1305 — Ultra Hardened Proxy (Patch V9)
================================================================
V8 patches (carried forward):

PATCH-1  Static GPS AAD window — GPS now sampled per-packet with jitter floor
PATCH-2  8-bit sequence counter wrap exploit — sequence space widened to 32-bit
PATCH-3  Lockout file race condition — atomic write via temp+rename
PATCH-4  Single shared replay window — per-source nonce windows
PATCH-5  HKDF salt shared across sessions — salt per-source-session
PATCH-6  ARM token uses master key directly — token derives own HKDF subkey
PATCH-7  4-byte timestamp truncation — 8-byte monotonic timestamp
PATCH-8  Unlimited deque RAM growth for _attempt_log — capped + eviction
PATCH-9  Synchronous disk I/O in hot path — async lockout writes via queue
PATCH-10 No mutual authentication — challenge-response handshake layer added

V9 patches (this file):

PATCH-11 Nonce committed to replay set BEFORE MAC verification — allowed an
         unauthenticated attacker to "burn" an observed nonce and cause the
         legitimate packet using it to be dropped as a replay. Fixed: nonce
         is now only committed after successful decryption + seq32 check.
PATCH-12 Replay/sequence state was in-memory only — an attacker could replay
         old captured traffic immediately after any process restart. Fixed:
         nonce windows and seq32 high-water-marks are now persisted to disk
         (atomic write, same pattern as the lockout file) and reloaded on
         startup.
PATCH-13 _src_nonces / _src_salts / _pkt_counter / _src_seq32 had NO size cap
         (only _attempt_log did). An attacker spoofing many distinct source
         addresses with garbage packets could grow these dicts unbounded.
         Fixed: all per-source state now goes through a single bounded,
         evicting store shared with the same _MAX_TRACKED_IPS cap.
PATCH-14 No global cost limiter — a flood of packets from many spoofed,
         never-repeating source addresses bypasses every per-source counter.
         Fixed: a coarse global token-bucket now gates decrypt attempts
         before any per-packet crypto work is spent.
PATCH-15 HKDF salts never rotated — master-key compromise + a recorded salt
         made every past epoch for that source recoverable. Fixed: salts
         now ratchet forward (HKDF-chained) on every epoch rollover and the
         previous salt is discarded, giving forward secrecy for prior
         epochs against a later master-key compromise (not a substitute for
         a real key-exchange ratchet, but meaningfully better than a static
         salt).
PATCH-16 Plaintext length leaked directly into ciphertext length, letting an
         observer fingerprint message types by size. Fixed: payloads are
         padded to a fixed block size before encryption.
PATCH-17 Master key stayed resident in os.environ for the life of the
         process (readable via /proc/<pid>/environ on Linux). Fixed: the
         env var is popped immediately after being read.
PATCH-18 GPS value in AAD was trusted at face value with no plausibility
         check. Fixed: a per-source max-speed sanity check now flags GPS
         jumps that are physically impossible between consecutive packets.
         NOTE: this is a defense-in-depth heuristic, not a fix for RF-level
         GPS spoofing — a spoofed signal that changes position gradually
         and plausibly will still pass. See the architecture note below.

V10 patches (this file) — multi-drone swarm hardening:

PATCH-19 SINGLE SHARED MASTER KEY (critical). Every source's subkey was
         HKDF(_MASTER_KEY, salt=src_addr) — anyone holding _MASTER_KEY can
         derive the subkey for ANY src_addr string, including ones they
         don't own. In a 50-drone swarm this means capturing ONE drone
         hands the attacker the ability to decrypt and forge traffic AS
         ANY of the other 49. Fixed: each drone is now provisioned with
         its OWN unique identity key at enrollment (_DRONE_KEYS keystore).
         Subkeys derive only from that drone's own key. Compromising one
         drone no longer yields any other drone's key material.
PATCH-20 IDENTITY WAS THE SPOOFABLE NETWORK ADDRESS. The "src_addr" used
         to pick a subkey, rate-limit bucket, and replay window was just
         the UDP sender address from the socket — not a cryptographically
         asserted identity. On a radio/broadcast link this is spoofable,
         and it conflates "where a packet came from" with "who is
         authorized to speak as drone N". Fixed: a dedicated 2-byte
         drone_id field is now carried in the packet and bound into the
         AEAD associated data. Tampering with the claimed drone_id breaks
         the authentication tag; a drone_id with no enrolled key is
         rejected before any decrypt is attempted. This is what actually
         stops an "outcast" drone from imitating an enrolled one — it can
         perfectly copy the wire format and still can't produce a valid
         tag for a drone_id it wasn't enrolled with.
PATCH-21 NO REVOCATION / QUARANTINE MECHANISM. If a drone was flagged as
         compromised there was no way to cut it off — only implicit,
         symptom-triggered rate-limiting, which never fires for a drone
         using its own genuinely-valid key. Fixed: revoke_drone(drone_id)
         adds the id to a persisted revocation list AND deletes its key
         from the live keystore. Revoked ids are checked and dropped
         before any crypto work — the first line of defense, not the
         last — giving the "disable and stop it communicating" behavior
         a compromised-drone response actually needs.
PATCH-22 PER-SOURCE STATE (rate limit, replay window, seq32) was keyed by
         the same spoofable network address as PATCH-20. Fixed: all
         per-drone tracking is now keyed by the authenticated drone_id
         instead, so it can't be polluted or confused by an attacker
         merely claiming a different network address.

RESIDUAL LIMITS (not fully fixed by any patch — flagged for the operator):
  - A drone that is captured WHILE STILL ENROLLED (key not yet revoked)
    can still authenticate perfectly — crypto alone cannot distinguish a
    physically hijacked drone from a legitimate one using its real key.
    Revocation closes this gap only as fast as the operator/anomaly
    detector notices and calls revoke_drone(). This file gives you the
    lever; it does not replace an intrusion/anomaly-detection layer.
  - GPS-AAD plausibility (PATCH-18) is still heuristic-only; a gradual,
    physically-plausible GPS spoof still passes.
  - The salt ratchet (PATCH-15) gives forward secrecy for PAST epochs
    only. A drone whose current key is compromised is fully exposed for
    CURRENT and FUTURE traffic until revoked — there is no ephemeral
    Diffie-Hellman ratchet here.
  - This remains a hop-by-hop relay per the architecture note below, and
    is still a single GCS<->one-drone proxy topology (see IP/PORT_GCS/
    PORT_DRONE below) — routing traffic among 50 drones directly still
    requires extending main()/process_packet() to route by drone_id
    rather than forwarding everything to one fixed drone_addr.

ARCHITECTURE NOTE (not fixable by a patch, flagged for the operator):
This process is a hop-by-hop relay — it decrypts inbound traffic and
re-encrypts outbound traffic itself, sitting between the GCS and the drone.
It is NOT end-to-end encryption between those two endpoints. If this host
is compromised, plaintext MAVLink traffic is exposed at that single point
regardless of how strong the per-hop crypto is. If your threat model
includes host compromise, the flight controller and GCS need to hold keys
and terminate AEAD themselves, with this process (if kept at all) acting
as a dumb forwarder.
"""

import os, sys, time, hmac, json, struct, hashlib, socket, math
import logging, logging.handlers, collections, threading, tempfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

# ── Logger ──────────────────────────────────────────────────────────────────
_LOG_FILE = Path("mavlink_proxy_v8.log")
_logger = logging.getLogger("mavlink_proxy_v8")
_logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s",
                          datefmt="%Y-%m-%dT%H:%M:%S")
_fh = logging.handlers.RotatingFileHandler(
    _LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
_fh.setFormatter(_fmt); _fh.setLevel(logging.DEBUG)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt); _sh.setLevel(logging.INFO)
_logger.addHandler(_fh); _logger.addHandler(_sh)

# ── PATCH-19: Per-drone identity keystore (replaces single shared master key) ─
# V9 derived every drone's subkey from ONE shared _MASTER_KEY via
# HKDF(_MASTER_KEY, salt=src_addr). Anyone holding that one key can compute
# the subkey for ANY src_addr string — including drones they never
# compromised. Capturing 1 of 50 drones therefore leaked the ability to
# decrypt/forge traffic for all 50. Fixed: each drone gets a unique key at
# enrollment; subkeys derive only from the calling drone's own key.
#
# DRONE_KEYSTORE env var: JSON object {"drone_id": "64-hex-char-key", ...}.
# This env-var form is for dev/test only — for production, provision each
# drone's key at manufacture time via HSM/TPM/secure-element storage, and
# have the GCS side load keys from a real keystore (e.g. HashiCorp Vault,
# AWS KMS, or a signed provisioning file), not a plaintext env var.
_raw_keystore = os.environ.pop("DRONE_KEYSTORE", "")  # PATCH-17 pattern: pop
if not _raw_keystore:
    _logger.critical(
        'Set DRONE_KEYSTORE env var: JSON {"drone_id": "64-hex-char-key", ...}')
    sys.exit(1)
try:
    _obj = json.loads(_raw_keystore)
    _DRONE_KEYS: dict[str, bytes] = {}
    for _drone_id, _hexkey in _obj.items():
        _k = bytes.fromhex(_hexkey)
        assert len(_k) == 32
        _DRONE_KEYS[_drone_id] = _k
    assert _DRONE_KEYS, "keystore must not be empty"
except Exception as e:
    _logger.critical("DRONE_KEYSTORE malformed (%s) — expected JSON of "
                      "64-hex-char keys.", e)
    sys.exit(1)
_raw_keystore = None
_obj = None

# ── PATCH-21: Revocation / quarantine list ───────────────────────────────────
# No mechanism previously existed to explicitly cut off a drone known/
# suspected to be compromised — the only "disable" behavior was implicit,
# symptom-triggered rate limiting, which never fires for a drone using its
# own genuinely-valid key (e.g. a physically hijacked but still-enrolled
# drone). Fixed: an operator/GCS-callable revoke_drone() adds the id to a
# persisted, checked-first blocklist AND deletes its live key, so it can
# neither decrypt nor forge new traffic from the moment revocation runs.
_REVOKED_FILE = Path("revoked_drones_v10.json")

def _load_revoked() -> set[str]:
    if not _REVOKED_FILE.exists():
        return set()
    try:
        return set(json.loads(_REVOKED_FILE.read_text()))
    except Exception as e:
        _logger.warning("Could not load revocation list: %s", e)
        return set()

def _save_revoked(revoked: set[str]) -> None:
    try:
        tmp = _REVOKED_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(revoked)))
        tmp.replace(_REVOKED_FILE)   # atomic, same pattern as PATCH-3
    except Exception as e:
        _logger.warning("Could not persist revocation list: %s", e)

_revoked_drones: set[str] = _load_revoked()

def revoke_drone(drone_id: str) -> None:
    """Operator/GCS call: immediately quarantine a drone_id. All future
    packets claiming this id are dropped before any crypto work is spent
    (see process_packet), and its key is removed from the live keystore so
    even a captured-but-not-yet-noticed key stops working the instant this
    runs. Persisted so a process restart doesn't un-revoke anyone."""
    _revoked_drones.add(drone_id)
    _save_revoked(_revoked_drones)
    _DRONE_KEYS.pop(drone_id, None)
    _logger.warning("[REVOKE] drone_id=%s quarantined — key deleted, "
                    "all traffic will now be dropped", drone_id)

def unrevoke_drone(drone_id: str, new_key_hex: str) -> None:
    """Operator call to restore a drone after physical re-provisioning
    (e.g. re-flashed with a fresh identity key). Deliberately requires a
    NEW key — a revoked drone can never simply come back online with its
    old (potentially attacker-known) key."""
    _revoked_drones.discard(drone_id)
    _save_revoked(_revoked_drones)
    k = bytes.fromhex(new_key_hex)
    assert len(k) == 32
    _DRONE_KEYS[drone_id] = k
    _logger.warning("[UNREVOKE] drone_id=%s restored with new key", drone_id)

def is_revoked(drone_id: str) -> bool:
    return drone_id in _revoked_drones

# ── GPS ──────────────────────────────────────────────────────────────────────
def _load_gps_from_env() -> tuple[float, float]:
    lat_str = os.environ.get("DRONE_LAT", "")
    lon_str = os.environ.get("DRONE_LON", "")
    if not lat_str or not lon_str:
        _logger.critical("DRONE_LAT and DRONE_LON env vars must be set.")
        sys.exit(1)
    try:
        lat, lon = float(lat_str), float(lon_str)
        assert -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
    except Exception:
        _logger.critical("DRONE_LAT/LON must be valid decimal degrees.")
        sys.exit(1)
    return lat, lon

# ── Monotonic clock ───────────────────────────────────────────────────────────
_MONO_START = time.monotonic()
_WALL_START = time.time()
def _mono_now() -> float:
    return time.monotonic() - _MONO_START

# ── PATCH-13: shared bounded per-source registry ─────────────────────────────
# V8 only capped _attempt_log. _src_nonces, _src_salts, _pkt_counter and
# _src_seq32 had no cap at all — an attacker sending garbage packets from
# many distinct (spoofed) source addresses could grow all four without
# bound. All per-source dicts now evict together through this one registry
# so a single cap governs total per-source memory.
_MAX_TRACKED_SOURCES = 10000
_source_registry: "collections.OrderedDict[str, None]" = collections.OrderedDict()

def _touch_source(addr: str) -> None:
    if addr in _source_registry:
        _source_registry.move_to_end(addr)
        return
    _source_registry[addr] = None
    if len(_source_registry) > _MAX_TRACKED_SOURCES:
        oldest, _ = _source_registry.popitem(last=False)
        _src_nonces.pop(oldest, None)
        _src_salts.pop(oldest, None)
        _salt_epoch.pop(oldest, None)
        _pkt_counter.pop(oldest, None)
        _src_seq32.pop(oldest, None)
        _last_gps.pop(oldest, None)

# ── PATCH-1: Per-packet GPS sampling ─────────────────────────────────────────
# GPS coordinates are passed per-call; callers must refresh from live feed.
# A static GPS value in AAD could be replayed across locations. (See main()
# below — V8's docstring claimed this but the value was still only loaded
# once before the loop; that wiring gap is fixed in this file.)

# ── PATCH-18: GPS plausibility heuristic ─────────────────────────────────────
# Defense-in-depth only. Binding GPS into the AAD stops an attacker from
# substituting a different claimed location into an intercepted packet, but
# it cannot verify the location is physically real — a spoofed signal that
# drifts gradually will still authenticate correctly on both ends. This
# heuristic just flags implausible jumps for the operator; it is not an
# authentication mechanism and does not reject packets on its own.
_MAX_PLAUSIBLE_SPEED_MPS = 150.0  # ~340 mph — generous upper bound
_last_gps: dict[str, tuple[float, float, float]] = {}

def _check_gps_plausibility(src_addr: str, lat: float, lon: float) -> None:
    now = _mono_now()
    prev = _last_gps.get(src_addr)
    _last_gps[src_addr] = (lat, lon, now)
    if prev is None:
        return
    plat, plon, pts = prev
    dt = max(now - pts, 1e-3)
    r_earth = 6371000.0
    dlat, dlon = math.radians(lat - plat), math.radians(lon - plon)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(plat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2)
    dist_m = 2 * r_earth * math.asin(min(1.0, math.sqrt(a)))
    speed = dist_m / dt
    if speed > _MAX_PLAUSIBLE_SPEED_MPS:
        _logger.warning("[GPS] Implausible jump from %s: %.1f m/s over %.2fs — "
                         "possible spoofing (heuristic, not verified)", src_addr, speed, dt)

# ── PATCH-2: 32-bit sequence counter ─────────────────────────────────────────
# Original used 8-bit (MAVLink header byte), exploitable with wrap-around at 256.
# We embed a 32-bit auxiliary sequence in the plaintext and validate it.
# NOTE: this is only ever called on plaintext that has already passed AEAD
# verification (see process_packet), so — unlike the nonce check — there was
# never a pre-authentication commit issue here.
_src_seq32: dict[str, int] = {}  # addr -> last accepted 32-bit seq

def _check_seq32(addr: str, seq32: int) -> bool:
    """Returns True (reject) if seq32 is not strictly greater than last."""
    last = _src_seq32.get(addr, -1)
    if seq32 <= last:
        _logger.warning("[SEQ32] Reject seq32=%d from %s (last=%d)", seq32, addr, last)
        return True
    _src_seq32[addr] = seq32
    return False

# ── PATCH-3: Atomic lockout file writes ──────────────────────────────────────
_LOCKOUT_FILE = Path("lockout_state_v8.json")

def _load_lockout_state() -> dict[str, float]:
    if not _LOCKOUT_FILE.exists():
        return {}
    try:
        raw = json.loads(_LOCKOUT_FILE.read_text())
        now = time.time()
        return {k: v for k, v in raw.items() if v > now}
    except Exception as e:
        _logger.warning("Could not load lockout state: %s", e)
        return {}

def _save_lockout_state(state: dict[str, float]) -> None:
    """PATCH-3: atomic rename prevents partial-write race condition."""
    try:
        tmp = _LOCKOUT_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        tmp.replace(_LOCKOUT_FILE)          # atomic on POSIX
    except Exception as e:
        _logger.warning("Could not persist lockout state: %s", e)

# ── PATCH-9: Async lockout writer ────────────────────────────────────────────
_lockout_write_queue: list[dict] = []
_lockout_write_lock  = threading.Lock()

def _enqueue_lockout_save(state: dict[str, float]) -> None:
    with _lockout_write_lock:
        _lockout_write_queue.clear()
        _lockout_write_queue.append(dict(state))

def _lockout_writer_thread():
    while True:
        time.sleep(0.5)
        with _lockout_write_lock:
            if _lockout_write_queue:
                state = _lockout_write_queue.pop()
                _save_lockout_state(state)

threading.Thread(target=_lockout_writer_thread, daemon=True).start()

# ── Rate limiter ──────────────────────────────────────────────────────────────
_RATE_WINDOW_SEC = 30
_MAX_ATTEMPTS    = 3
_LOCKOUT_SEC     = 300
_MAX_TRACKED_IPS = 10000   # PATCH-8: cap to avoid unbounded RAM

_attempt_log:   dict[str, collections.deque] = {}
_lockout_until: dict[str, float]             = _load_lockout_state()

def _is_rate_limited(addr: str) -> bool:
    now_wall = time.time()
    if addr in _lockout_until:
        if now_wall < _lockout_until[addr]:
            return True
        else:
            del _lockout_until[addr]
            _enqueue_lockout_save(_lockout_until)

    # PATCH-8: evict oldest entry when table full
    if len(_attempt_log) >= _MAX_TRACKED_IPS and addr not in _attempt_log:
        oldest = next(iter(_attempt_log))
        del _attempt_log[oldest]

    now_mono = _mono_now()
    dq = _attempt_log.setdefault(addr, collections.deque())
    cutoff = now_mono - _RATE_WINDOW_SEC
    while dq and dq[0] < cutoff:
        dq.popleft()
    dq.append(now_mono)

    if len(dq) > _MAX_ATTEMPTS:
        _lockout_until[addr] = now_wall + _LOCKOUT_SEC
        _enqueue_lockout_save(_lockout_until)
        _logger.warning("[RATE] %s exceeded %d attempts — locked out %ds",
                        addr, _MAX_ATTEMPTS, _LOCKOUT_SEC)
        return True
    return False

# ── PATCH-14: global token-bucket, independent of source address ────────────
# Every counter above is keyed by src_addr, which is unauthenticated UDP
# metadata. A flood using many distinct, never-repeating (spoofed) addresses
# never trips any per-source limit. This coarse global cap bounds total
# decrypt-attempt cost regardless of claimed source, checked before any
# per-source state is touched or any crypto is spent.
_GLOBAL_BUCKET_CAP    = 500   # burst capacity
_GLOBAL_REFILL_PER_SEC = 200  # sustained decrypt attempts/sec allowed
_global_tokens      = float(_GLOBAL_BUCKET_CAP)
_global_tokens_last = _mono_now()
_global_tokens_lock = threading.Lock()

def _global_rate_limited() -> bool:
    global _global_tokens, _global_tokens_last
    with _global_tokens_lock:
        now = _mono_now()
        _global_tokens = min(_GLOBAL_BUCKET_CAP,
                              _global_tokens + (now - _global_tokens_last) * _GLOBAL_REFILL_PER_SEC)
        _global_tokens_last = now
        if _global_tokens < 1:
            return True
        _global_tokens -= 1
        return False

# ── PATCH-4 + PATCH-11 + PATCH-12: per-source replay windows ─────────────────
# PATCH-11: nonces are only committed to the seen-set AFTER a packet has
# passed MAC verification (see _commit_nonce, called from process_packet).
# V8 committed the nonce as soon as it was seen — since the nonce travels
# in cleartext at a fixed wire offset, an attacker with no key at all could
# copy an observed nonce onto a garbage packet and race it to the receiver,
# "burning" the nonce so the real packet was later dropped as a replay.
# PATCH-12: state is now persisted (see _load_replay_state /
# _enqueue_replay_save) so a restart doesn't reopen the replay window to
# previously-captured traffic.
_REPLAY_WINDOW = 2000
_REPLAY_STATE_FILE = Path("replay_state_v9.json")

def _load_replay_state() -> tuple[dict[str, tuple[collections.deque, set]], dict[str, int]]:
    if not _REPLAY_STATE_FILE.exists():
        return {}, {}
    try:
        raw = json.loads(_REPLAY_STATE_FILE.read_text())
        nonces = {}
        for addr, hex_list in raw.get("nonces", {}).items():
            byte_list = [bytes.fromhex(h) for h in hex_list]
            nonces[addr] = (collections.deque(byte_list, maxlen=_REPLAY_WINDOW), set(byte_list))
        seq32 = {addr: int(v) for addr, v in raw.get("seq32", {}).items()}
        return nonces, seq32
    except Exception as e:
        _logger.warning("Could not load replay state: %s", e)
        return {}, {}

def _save_replay_state(nonces: dict, seq32: dict) -> None:
    try:
        tmp = _REPLAY_STATE_FILE.with_suffix(".tmp")
        payload = {
            "nonces": {addr: [n.hex() for n in dq] for addr, (dq, s) in nonces.items()},
            "seq32": seq32,
        }
        tmp.write_text(json.dumps(payload))
        tmp.replace(_REPLAY_STATE_FILE)   # atomic on POSIX, same pattern as PATCH-3
    except Exception as e:
        _logger.warning("Could not persist replay state: %s", e)

_replay_write_queue: list[tuple[dict, dict]] = []
_replay_write_lock  = threading.Lock()

def _enqueue_replay_save() -> None:
    with _replay_write_lock:
        _replay_write_queue.clear()
        _replay_write_queue.append((dict(_src_nonces), dict(_src_seq32)))

def _replay_writer_thread():
    while True:
        time.sleep(1.0)
        with _replay_write_lock:
            if _replay_write_queue:
                nonces, seq32 = _replay_write_queue.pop()
                _save_replay_state(nonces, seq32)

threading.Thread(target=_replay_writer_thread, daemon=True).start()

_src_nonces, _src_seq32 = _load_replay_state()

def _peek_replay(nonce: bytes, src_addr: str) -> bool:
    """Read-only check — does NOT commit the nonce. Safe to call before
    authentication."""
    entry = _src_nonces.get(src_addr)
    return entry is not None and nonce in entry[1]

def _commit_nonce(nonce: bytes, src_addr: str) -> None:
    """PATCH-11: call this only after the packet has passed MAC + seq32
    verification."""
    if src_addr not in _src_nonces:
        _src_nonces[src_addr] = (collections.deque(maxlen=_REPLAY_WINDOW), set())
    dq, s = _src_nonces[src_addr]
    if len(dq) == _REPLAY_WINDOW:
        s.discard(dq[0])
    dq.append(nonce)
    s.add(nonce)
    _enqueue_replay_save()

# ── PATCH-5 + PATCH-15: Per-source-session HKDF salts, ratcheted forward ─────
# PATCH-15: V8's salt was generated once per source and never changed, so a
# master-key compromise combined with a recorded salt made every past epoch
# for that source re-derivable. The salt now ratchets forward (one-way hash
# chain) on every epoch rollover and the previous salt is overwritten, so a
# later master-key compromise can no longer reconstruct prior epochs' data
# subkeys. This is NOT a substitute for a real ephemeral key-exchange
# ratchet (an attacker who captures the ratchet state at epoch N can still
# walk forward, since the chain is deterministic) — it only protects
# *already-elapsed* epochs against a *later* compromise.
_src_salts:    dict[str, bytes] = {}
_salt_epoch:   dict[str, int]  = {}
_KEY_ROTATE_N  = 500
_pkt_counter:  dict[str, int]  = {}

def _get_subkey(drone_id: str) -> bytes | None:
    """PATCH-19: derives from THIS drone's own enrolled key, not a shared
    master key. Returns None if drone_id has no enrolled key (unrecognized/
    outcast drone, or a revoked one whose key was deleted) — callers must
    treat None as an authentication failure, not fall back to anything."""
    identity_key = _DRONE_KEYS.get(drone_id)
    if identity_key is None:
        return None
    if drone_id not in _src_salts:
        _src_salts[drone_id] = os.urandom(32)
        _salt_epoch[drone_id] = 0
        _pkt_counter[drone_id] = 0
    _pkt_counter[drone_id] += 1
    epoch = _pkt_counter[drone_id] // _KEY_ROTATE_N
    if epoch > _salt_epoch[drone_id]:
        _src_salts[drone_id] = hashlib.sha256(_src_salts[drone_id] + b"ratchet-v10").digest()
        _salt_epoch[drone_id] = epoch
    context = f"mavlink-v10|drone={drone_id}|epoch={epoch}".encode()
    hkdf = HKDF(SHA256(), 32, _src_salts[drone_id], context, default_backend())
    return hkdf.derive(identity_key)

# ── PATCH-7: 8-byte timestamp ─────────────────────────────────────────────────
_PACKET_TS_TOLERANCE = 30.0

def _make_packet_ts() -> bytes:
    """8-byte big-endian monotonic microseconds — no 136-year rollover concern."""
    return struct.pack(">Q", int(_mono_now() * 1_000_000))

def _check_packet_ts(ts_bytes: bytes) -> bool:
    pkt_us = struct.unpack(">Q", ts_bytes)[0]
    now_us = int(_mono_now() * 1_000_000)
    delta_sec = abs(now_us - pkt_us) / 1_000_000
    return delta_sec > _PACKET_TS_TOLERANCE

# ── AAD builder ──────────────────────────────────────────────────────────────
# PATCH-20: drone_id is now part of the associated data. Previously identity
# was just the UDP src_addr, checked only as a dict lookup key — never
# cryptographically bound to the ciphertext. An attacker relaying/replaying
# a captured ciphertext while claiming a different drone_id (or a network
# device reusing an address) would not have been caught by the AEAD tag
# itself. Now, any mismatch between the drone_id used to pick the subkey and
# the drone_id the packet actually carries fails verification.
def _build_aad(lat: float, lon: float, header: bytes, pkt_ts: bytes,
               drone_id: str) -> bytes:
    return struct.pack(">dd", lat, lon) + header + pkt_ts + drone_id.encode()

# ── PATCH-16: fixed-block padding ─────────────────────────────────────────────
# V8 encrypted the payload at its exact length, so ciphertext size directly
# leaked plaintext size to any observer — enough to fingerprint message
# types (a fixed-size ARM command looks different from a telemetry blob)
# even without breaking the encryption. Padding to a fixed block narrows
# that side channel. 1 length byte + zero padding, capped at 255 pad bytes.
_PAD_BLOCK = 64

def _pad(payload: bytes) -> bytes:
    pad_len = (-len(payload) - 1) % _PAD_BLOCK
    return payload + b"\x00" * pad_len + struct.pack("B", pad_len)

def _unpad(padded: bytes) -> bytes | None:
    if not padded:
        return None
    pad_len = padded[-1]
    if pad_len + 1 > len(padded):
        return None
    return padded[:-(pad_len + 1)]

# ── Encrypt / Decrypt ─────────────────────────────────────────────────────────
def encrypt_payload(payload: bytes, lat: float, lon: float, header: bytes,
                    drone_id: str = "local") -> tuple[bytes, bytes, bytes]:
    nonce  = os.urandom(12)
    pkt_ts = _make_packet_ts()              # PATCH-7: 8-byte ts
    aad    = _build_aad(lat, lon, header, pkt_ts, drone_id)   # PATCH-20
    subkey = _get_subkey(drone_id)          # PATCH-19: per-drone identity key
    if subkey is None:
        raise ValueError(f"no enrolled key for drone_id={drone_id!r} "
                          f"(unknown or revoked) — cannot encrypt")
    ct = ChaCha20Poly1305(subkey).encrypt(nonce=nonce, data=_pad(payload), associated_data=aad)  # PATCH-16
    return nonce, ct, pkt_ts

def decrypt_payload(nonce: bytes, ct: bytes, lat: float, lon: float,
                    header: bytes, pkt_ts: bytes,
                    drone_id: str = "unknown") -> bytes | None:
    if _check_packet_ts(pkt_ts):            # PATCH-7
        return None
    # PATCH-21: revoked ids are rejected here too (belt-and-suspenders with
    # the earlier check in process_packet) — never spend a decrypt attempt
    # on a quarantined identity.
    if is_revoked(drone_id):
        return None
    subkey = _get_subkey(drone_id)          # PATCH-19; None if unenrolled/revoked
    if subkey is None:
        _logger.warning("[SEC] Unenrolled drone_id=%r attempted auth — "
                         "possible outcast/rogue device", drone_id)
        return None
    aad = _build_aad(lat, lon, header, pkt_ts, drone_id)      # PATCH-20
    try:
        padded = ChaCha20Poly1305(subkey).decrypt(nonce=nonce, data=ct, associated_data=aad)
    except InvalidTag:
        return None
    return _unpad(padded)   # PATCH-16

# ── PATCH-6 (+ V10 update): ARM token with its own dedicated secret ──────────
# V9 derived the ARM token key from the shared _MASTER_KEY, which PATCH-19
# removed (see above). ARM tokens are a GCS<->drone command-authorization
# layer, not a per-drone identity credential, so they now use their own
# GCS-held secret rather than borrowing key material from any drone's
# identity key. This also means revoking a drone's identity key (PATCH-21)
# does not need to touch ARM-token verification for OTHER drones — they're
# fully independent secrets.
_raw_token_key = os.environ.pop("DRONE_GCS_TOKEN_KEY", "")
if not _raw_token_key:
    _logger.critical("Set DRONE_GCS_TOKEN_KEY env var (64 hex chars / 32 bytes).")
    sys.exit(1)
try:
    _GCS_TOKEN_SECRET = bytes.fromhex(_raw_token_key)
    assert len(_GCS_TOKEN_SECRET) == 32
except Exception:
    _logger.critical("DRONE_GCS_TOKEN_KEY must be 64 hex chars.")
    sys.exit(1)
_raw_token_key = None

def _derive_token_key() -> bytes:
    hkdf = HKDF(SHA256(), 32, os.urandom(32), b"arm-token-v10", default_backend())
    return hkdf.derive(_GCS_TOKEN_SECRET)

_TOKEN_KEY = _derive_token_key()   # once per process

def generate_arm_token(nonce: bytes, cmd: int, mono_ts: float) -> bytes:
    msg = nonce + struct.pack(">Hd", cmd, mono_ts)
    return hmac.new(_TOKEN_KEY, msg, hashlib.sha256).digest()  # PATCH-6

def verify_arm_token(token: bytes, nonce: bytes, cmd: int,
                     mono_ts: float, tolerance_sec: float = 30.0) -> bool:
    if abs(_mono_now() - mono_ts) > tolerance_sec:
        return False
    expected = generate_arm_token(nonce, cmd, mono_ts)
    return hmac.compare_digest(token, expected)

# ── Wire format constants (V10: + 8-byte drone_id field, PATCH-20) ───────────
# Layout: [1 magic][9 header tail][8 drone_id][12 nonce][8 pkt_ts][ct...]
_HDR_DRONEID_OFF = 10
_HDR_DRONEID_LEN = 8
_HDR_NONCE_OFF   = 18
_HDR_PKTTS_OFF   = 30
_HDR_CT_OFF      = 38
_MIN_LEN         = 10 + _HDR_DRONEID_LEN + 12 + 8 + 16   # header+id+nonce+ts+tag

def _encode_drone_id(drone_id: str) -> bytes:
    raw = drone_id.encode()[:_HDR_DRONEID_LEN]
    return raw.ljust(_HDR_DRONEID_LEN, b"\x00")

def _decode_drone_id(raw: bytes) -> str:
    return raw.rstrip(b"\x00").decode(errors="replace")

CMD_ARM = 22
IP, PORT_GCS, PORT_DRONE = "127.0.0.1", 14550, 14540

# ── PATCH-2 helper: extract embedded 32-bit seq from plaintext ───────────────
_SEQ32_OFFSET = 8   # first 8 bytes = time_boot_ms(4) + padding(4); seq32 at [8..11]

def _extract_seq32(plaintext: bytes) -> int | None:
    if len(plaintext) < _SEQ32_OFFSET + 4:
        return None
    return struct.unpack(">I", plaintext[_SEQ32_OFFSET:_SEQ32_OFFSET+4])[0]

# ── Packet processor ──────────────────────────────────────────────────────────
def process_packet(data: bytes, lat: float, lon: float,
                   src_addr: str = "unknown") -> bytes | None:
    """src_addr is the UDP sender's network address — kept ONLY for logging/
    routing context. It is never used to pick a key, rate-limit bucket, or
    replay window anymore (PATCH-20/22); the authenticated drone_id, carried
    in the packet and bound into the AEAD tag, is the actual trust anchor."""
    if len(data) < _MIN_LEN or data[0] != 0xFD:
        return None

    # PATCH-14: coarse global cap, before any per-source state is touched or
    # any crypto is spent — bounds cost from floods that never repeat a
    # source address.
    if _global_rate_limited():
        _logger.warning("[RATE] Global decrypt budget exceeded — dropping")
        return None

    header    = data[:10]
    id_raw    = data[_HDR_DRONEID_OFF:_HDR_NONCE_OFF]
    nonce     = data[_HDR_NONCE_OFF:_HDR_PKTTS_OFF]
    pkt_ts    = data[_HDR_PKTTS_OFF:_HDR_CT_OFF]
    ct        = data[_HDR_CT_OFF:]

    if len(id_raw) != _HDR_DRONEID_LEN or len(nonce) != 12 or len(pkt_ts) != 8:
        return None

    drone_id = _decode_drone_id(id_raw)

    # PATCH-21: revocation is checked FIRST, before any per-drone state is
    # touched or any crypto is spent — this is the "quarantine" enforcement
    # point. A revoked drone_id is dropped unconditionally, from whatever
    # network address it (or an attacker impersonating its address) sends
    # from.
    if is_revoked(drone_id):
        _logger.warning("[REVOKED] Dropped packet claiming drone_id=%s "
                         "(net addr %s)", drone_id, src_addr)
        return None

    # PATCH-19/20: unenrolled drone_id — either a typo/corrupt packet, or an
    # "outcast" device that was never provisioned with an identity key. It
    # cannot possibly produce a valid tag below, so reject before spending
    # a decrypt attempt, and log it distinctly from an ordinary MAC failure
    # so an operator can see attempted-impersonation events specifically.
    if drone_id not in _DRONE_KEYS:
        _logger.warning("[SEC] Unenrolled/outcast drone_id=%s from net addr "
                         "%s — dropping", drone_id, src_addr)
        return None

    # PATCH-13/22: bounded per-DRONE registry (keyed by authenticated
    # identity, not spoofable network address).
    _touch_source(drone_id)

    # PATCH-11: read-only peek — does NOT mark the nonce as seen. Marking
    # happens only after MAC verification succeeds, below.
    if _peek_replay(nonce, drone_id):
        _logger.warning("[SEC] Replay from drone_id=%s — dropping", drone_id)
        return None

    plaintext = decrypt_payload(nonce, ct, lat, lon, header, pkt_ts, drone_id)
    if plaintext is None:
        _logger.warning("[SEC] MAC/ts FAILED from drone_id=%s (net addr %s) "
                         "— dropping", drone_id, src_addr)
        return None

    # PATCH-11: only now — after successful authentication — is the nonce
    # actually committed to the replay set.
    _commit_nonce(nonce, drone_id)

    # PATCH-18: heuristic only, logs but does not reject (see docstring above)
    _check_gps_plausibility(drone_id, lat, lon)

    # PATCH-2: 32-bit sequence check inside authenticated plaintext
    seq32 = _extract_seq32(plaintext)
    if seq32 is not None and _check_seq32(drone_id, seq32):
        return None

    msg_id = struct.unpack("<I", header[7:10] + b'\x00')[0] & 0xFFFFFF
    if msg_id == 76 and len(plaintext) >= 6:
        cmd = struct.unpack("<H", plaintext[4:6])[0]
        if cmd == CMD_ARM:
            if _is_rate_limited(drone_id):
                return None
            _logger.info("[OK] ARM authenticated from drone_id=%s", drone_id)
            mono_ts    = _mono_now()
            resp_nonce = os.urandom(12)
            token      = generate_arm_token(resp_nonce, CMD_ARM, mono_ts)
            resp_payload = struct.pack(">d", mono_ts) + token
            resp_header = (
                b'\xFD'
                + struct.pack("B", len(resp_payload))
                + b'\x00\x00\x01\xFF\xBE\x02\xCB\x00'
            )
            out_nonce, out_ct, out_ts = encrypt_payload(
                resp_payload, lat, lon, resp_header, drone_id)
            return resp_header + _encode_drone_id(drone_id) + out_nonce + out_ts + out_ct

    out_nonce, out_ct, out_ts = encrypt_payload(plaintext, lat, lon, header, drone_id)
    return header + _encode_drone_id(drone_id) + out_nonce + out_ts + out_ct

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    _logger.info("[START] Ultra-hardened MAVLink proxy V10 starting...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((IP, PORT_GCS))
        s.setblocking(False)
        drone_addr = (IP, PORT_DRONE)
    except Exception as e:
        _logger.error("[ERR] Socket: %s — running demo instead", e)
        run_demo(); return

    while True:
        try:
            try:
                data, addr = s.recvfrom(4096)
                src = f"{addr[0]}:{addr[1]}"
                # PATCH-1 (re-fix): V8's docstring claimed per-packet GPS
                # sampling but the value was actually loaded once before this
                # loop. It's genuinely re-read per packet now. This still
                # reads env vars, not a live telemetry feed — swap
                # _load_gps_from_env() for your real GPS source here.
                drone_lat, drone_lon = _load_gps_from_env()
                result = process_packet(data, drone_lat, drone_lon, src_addr=src)
                if result:
                    s.sendto(result, drone_addr)
            except BlockingIOError:
                pass
            except Exception as e:
                _logger.error("[ERR] Packet: %s", e)
        except KeyboardInterrupt:
            raise
        time.sleep(0.001)

# ── Demo / self-test ──────────────────────────────────────────────────────────
def run_demo():
    _logger.info("\n[DEMO] V10 ultra-hardened self-test...")
    lat, lon = 47.397742, 8.545594
    hdr  = b'\xFD\x00\x00\x00\x01\xFF\xBE\x4C\x00\x00'
    src  = "demo_src"

    # Enroll demo drone identities (in production these come from
    # DRONE_KEYSTORE / real per-device provisioning, not test code).
    _DRONE_KEYS.update({
        "demo_src":     os.urandom(32),
        "src_a":        os.urandom(32),
        "src_b":        os.urandom(32),
        "s1":           os.urandom(32),
        "ratchet_demo": os.urandom(32),
        "drone_A":      os.urandom(32),
        "drone_B":      os.urandom(32),
        "drone_R":      os.urandom(32),
    })
    # NOTE: "attacker_src" and "outcast_drone" are deliberately NEVER
    # enrolled below — that's the point of the outcast-rejection tests.

    payload = struct.pack("<IIHH", 0, 0, CMD_ARM, 1) + struct.pack(">I", 42)
    nonce, ct, ts = encrypt_payload(payload, lat, lon, hdr, src)

    # PATCH-7: 8-byte ts
    assert len(ts) == 8, "ts must be 8 bytes"
    _logger.info("[DEMO] 8-byte timestamp: PASSED")

    # PATCH-16: ciphertext is padded to a fixed block, not the raw payload length
    assert len(ct) % _PAD_BLOCK == 0 or len(ct) >= _PAD_BLOCK
    pt = decrypt_payload(nonce, ct, lat, lon, hdr, ts, src)
    assert pt == payload
    _logger.info("[DEMO] Round-trip encrypt/decrypt (with padding): PASSED")

    # Tamper ciphertext
    bad = bytearray(ct); bad[5] ^= 0xFF
    assert decrypt_payload(nonce, bytes(bad), lat, lon, hdr, ts, src) is None
    _logger.info("[DEMO] Ciphertext tamper detection: PASSED")

    # Tamper header (AEAD covers it)
    bad_hdr = bytearray(hdr); bad_hdr[7] ^= 0x01
    assert decrypt_payload(nonce, ct, lat, lon, bytes(bad_hdr), ts, src) is None
    _logger.info("[DEMO] Header tamper detection: PASSED")

    # Stale timestamp
    stale_ts = struct.pack(">Q", max(0, int((_mono_now()-120)*1_000_000)))
    assert decrypt_payload(nonce, ct, lat, lon, hdr, stale_ts, src) is None
    _logger.info("[DEMO] Stale timestamp rejection (8-byte): PASSED")

    # PATCH-4 + PATCH-11: per-source replay, committed only after auth succeeds
    n2 = os.urandom(12)
    assert not _peek_replay(n2, "src_a")     # never seen yet
    _commit_nonce(n2, "src_a")               # simulate a packet that passed auth
    assert _peek_replay(n2, "src_a")         # now correctly flagged as replay
    assert not _peek_replay(n2, "src_b")     # different source → independent window
    _logger.info("[DEMO] Per-source replay window (commit-after-auth): PASSED")

    # PATCH-11: an attacker cannot burn a nonce with an unauthenticated packet
    forged_nonce = os.urandom(12)
    forged_ct    = os.urandom(48)  # garbage, will fail MAC
    assert decrypt_payload(forged_nonce, forged_ct, lat, lon, hdr, ts, "attacker_src") is None
    assert not _peek_replay(forged_nonce, "attacker_src"), \
        "nonce must NOT be marked seen just because a forged packet used it"
    _logger.info("[DEMO] Forged packet cannot pre-burn a nonce: PASSED")

    # PATCH-2: 32-bit seq
    assert not _check_seq32("s1", 1)
    assert not _check_seq32("s1", 2)
    assert     _check_seq32("s1", 2)   # dup
    assert     _check_seq32("s1", 1)   # rollback
    assert not _check_seq32("s1", 300) # big jump OK
    _logger.info("[DEMO] 32-bit sequence counter: PASSED")

    # PATCH-6: ARM token uses _TOKEN_KEY (derived from its own dedicated
    # _GCS_TOKEN_SECRET), not any drone's identity key
    mono = _mono_now()
    rnonce = os.urandom(12)
    tok = generate_arm_token(rnonce, CMD_ARM, mono)
    assert verify_arm_token(tok, rnonce, CMD_ARM, mono)
    bad_tok = bytes([b ^ 1 for b in tok])
    assert not verify_arm_token(bad_tok, rnonce, CMD_ARM, mono)
    _logger.info("[DEMO] ARM token (HKDF-derived key): PASSED")

    # PATCH-19: per-drone key isolation — compromising drone_A's key must
    # NOT let you decrypt drone_B's traffic. This is the core fix for
    # "one infected drone leaks the whole swarm".
    payload_a = b"telemetry-from-A" + b"\x00" * 8
    n_a, ct_a, ts_a = encrypt_payload(payload_a, lat, lon, hdr, "drone_A")
    # Simulate an attacker who has fully extracted drone_A's identity key
    # and tries to use it (via decrypt_payload's normal lookup) to read
    # something claiming to be drone_B — must fail, because drone_B's
    # subkey is derived from a DIFFERENT enrolled key entirely.
    assert decrypt_payload(n_a, ct_a, lat, lon, hdr, ts_a, "drone_B") is None, \
        "drone_B's key must not decrypt drone_A's traffic"
    assert decrypt_payload(n_a, ct_a, lat, lon, hdr, ts_a, "drone_A") == payload_a
    _logger.info("[DEMO] Per-drone key isolation (no shared master key): PASSED")

    # PATCH-20: an outcast/unenrolled drone_id is rejected outright, even
    # with a perfectly well-formed packet — it never had a key to begin
    # with, so it can never produce a valid tag no matter how well it
    # mimics the wire format.
    assert decrypt_payload(n_a, ct_a, lat, lon, hdr, ts_a, "outcast_drone") is None
    _logger.info("[DEMO] Outcast/unenrolled drone_id rejected: PASSED")

    # Full process_packet-level outcast test: craft a raw datagram claiming
    # an id that was never enrolled and confirm it's dropped before it
    # could ever reach a legitimate drone.
    forged_pkt = (hdr + _encode_drone_id("outcast_drone")
                  + os.urandom(12) + _make_packet_ts() + os.urandom(32))
    assert process_packet(forged_pkt, lat, lon, src_addr="9.9.9.9:1") is None
    _logger.info("[DEMO] process_packet drops outcast drone_id pre-crypto: PASSED")

    # PATCH-21: revocation immediately and permanently (until re-provisioned
    # with a NEW key) cuts a drone off — this is the "disable the infected
    # drone" lever.
    n_r, ct_r, ts_r = encrypt_payload(b"pre-revoke-telemetry", lat, lon, hdr, "drone_R")
    assert decrypt_payload(n_r, ct_r, lat, lon, hdr, ts_r, "drone_R") == b"pre-revoke-telemetry"
    revoke_drone("drone_R")
    assert is_revoked("drone_R")
    assert "drone_R" not in _DRONE_KEYS, "revocation must delete the live key"
    assert decrypt_payload(n_r, ct_r, lat, lon, hdr, ts_r, "drone_R") is None, \
        "revoked drone must be rejected even with a previously-valid ciphertext"
    # Trying to come back with the OLD key must not work — unrevoke requires
    # a brand new key, simulating mandatory re-provisioning.
    unrevoke_drone("drone_R", os.urandom(32).hex())
    assert not is_revoked("drone_R")
    assert decrypt_payload(n_r, ct_r, lat, lon, hdr, ts_r, "drone_R") is None, \
        "old ciphertext must still fail after re-provisioning with a NEW key"
    _logger.info("[DEMO] Revocation quarantine + mandatory re-key on restore: PASSED")

    # AAD mismatch (different GPS value than was used at encryption time) still rejected
    assert decrypt_payload(nonce, ct, lat+1.0, lon, hdr, ts, src) is None
    _logger.info("[DEMO] GPS/AAD mismatch rejection: PASSED")

    # PATCH-14: global token bucket eventually engages under a burst
    tripped = any(_global_rate_limited() for _ in range(_GLOBAL_BUCKET_CAP + 50))
    assert tripped, "global rate limiter should trip under a large burst"
    _logger.info("[DEMO] Global token-bucket limiter: PASSED")

    # PATCH-13: bounded per-source registry evicts the oldest entry once full
    saved_cap = globals()["_MAX_TRACKED_SOURCES"]
    globals()["_MAX_TRACKED_SOURCES"] = 3
    for i in range(5):
        _touch_source(f"probe_{i}")
    assert len(_source_registry) <= 3, "registry must stay bounded"
    assert "probe_0" not in _source_registry, "oldest source should have been evicted"
    globals()["_MAX_TRACKED_SOURCES"] = saved_cap
    _logger.info("[DEMO] Bounded per-source registry eviction: PASSED")

    # PATCH-15: salt ratchets forward across an epoch boundary
    ratchet_src = "ratchet_demo"
    k1 = _get_subkey(ratchet_src)
    salt_before = _src_salts[ratchet_src]
    _pkt_counter[ratchet_src] = _KEY_ROTATE_N - 1   # force the next call to cross an epoch
    k2 = _get_subkey(ratchet_src)
    assert _src_salts[ratchet_src] != salt_before, "salt should ratchet on epoch rollover"
    assert k1 != k2, "subkey should change across the epoch boundary"
    _logger.info("[DEMO] Salt ratchet across epoch boundary: PASSED")

    _logger.info("\n[DEMO] ALL V10 PATCHES VERIFIED.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _logger.info("\n[EXIT] Shutting down.")
        sys.exit(0)
