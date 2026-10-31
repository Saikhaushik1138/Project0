"""Offline demo; never opens a socket or sends a flight command."""
import argparse
import secrets

from .channel import PacketError, SecureChannel, load_key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo", "keygen"])
    args = parser.parse_args()
    if args.command == "keygen":
        print(secrets.token_hex(32))
        return
    try:
        key = load_key()
    except ValueError as exc:
        parser.error(str(exc))
    sender = SecureChannel(key, context=b"project0/demo/gcs-to-uav")
    receiver = SecureChannel(key, context=b"project0/demo/gcs-to-uav")
    payload = b"SIMULATION ONLY: telemetry sample"
    packet = sender.seal(payload)
    decoded = receiver.open(packet)
    if decoded != payload:
        raise RuntimeError("round-trip payload mismatch")
    print(f"PASS: encrypted round trip ({len(payload)} payload bytes, {len(packet)} envelope bytes)")
    tampered = packet[:-1] + bytes([packet[-1] ^ 1])
    for label, candidate in [("tampering", tampered), ("replay", packet)]:
        try:
            receiver.open(candidate)
        except PacketError:
            print(f"PASS: {label} rejected")
        else:
            raise RuntimeError(f"{label} was accepted")


if __name__ == "__main__":
    main()
