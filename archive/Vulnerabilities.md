# Software Attacks

## 1. Eavesdropping Attack

In this attack, an attacker listens to the communication between the Ground Control Station (GCS) and the UAV to capture transmitted data.
The message is encrypted using ChaCha20 before transmission, so the intercepted packet only contains ciphertext.

### Result
The attacker cannot read any plaintext information from the captured packet.

## 2. Packet Tampering Attack

In this attack, one or more bits of an encrypted packet are modified before it reaches the receiver.
Poly1305 verifies the integrity of every received packet. Even a single-bit modification changes the authentication tag.

### Result
The modified packet fails authentication and is discarded.

## 3. Forged Packet Attack

An attacker creates a completely fake encrypted packet and sends it to the receiver.
Since the attacker does not possess the secret key, a valid Poly1305 authentication tag cannot be generated.

### Result
The forged packet is rejected by the receiver.

## 4. Man-in-the-Middle (MITM) Injection

The attacker intercepts the communication, modifies the packet, and forwards it to the receiver.
Every encrypted packet is authenticated before decryption. Any modification causes authentication failure.

### Result
The modified packet is detected and dropped.

## 5. Command Spoofing Attack

The attacker attempts to send fake drone commands pretending to be the Ground Control Station.
Only packets authenticated using the correct secret key are accepted by the receiver.

### Result
Unauthorized commands are rejected.

## 6. Replay Attack

A previously captured valid packet is transmitted again by the attacker.
The receiver stores previously used nonces and rejects duplicate ones.

### Result
Replayed packets are detected immediately.

## 7. Predictable Nonce Attack

This attack checks whether the generated nonces follow a predictable pattern.
Cryptographically secure random nonce generation ensures that every encryption uses a unique nonce.

### Result
All generated nonces remain unique.

## 8. Token Brute Force Attack

The attacker repeatedly guesses authentication tokens hoping to obtain a valid one.
The authentication token has a large key space, making random guessing practically impossible.

### Result
No valid token was successfully guessed.

## 9. Stale Token Replay Attack

An attacker attempts to authenticate using an expired authentication token.
Each token is checked against its validity period before authentication.

### Result
Expired tokens are rejected.

## 10. Rate-Limit / Lockout Attack

This attack performs repeated authentication attempts within a short period.
After multiple failed attempts, the system temporarily blocks further requests.

### Result
Repeated attempts are automatically locked out.

## 11. GPS AAD Tampering Attack

In this attack, the GPS coordinates included as Additional Authenticated Data (AAD) are modified.
The GPS coordinates are authenticated together with the encrypted message. Any change causes authentication failure.

### Result
The tampered packet is rejected.

## 12. Hardcoded Key Discovery

The source code is inspected to check whether encryption keys are stored directly in the program.
The implementation loads cryptographic keys securely instead of embedding them in the source code.

### Result
No hardcoded encryption keys were found.

## 13. Nonce Reuse Catastrophe

This attack checks whether the same nonce is reused during multiple encryptions, which can weaken stream cipher security.
A fresh random nonce is generated for every encryption operation, even when encrypting identical messages.

# Hardware Attacks

## 1. RF Jamming

An attacker transmits high-power radio signals to interfere with communication between the Ground Control Station and the UAV.

This attack cannot be prevented by encryption because the communication channel itself is disrupted. Hardware-based techniques such as Frequency Hopping Spread Spectrum (FHSS) are required.

### Result
Communication becomes unavailable until the interference is removed.

## 2. GPS Spoofing

An attacker broadcasts fake GPS signals that are stronger than the legitimate satellite signals, causing the UAV to calculate an incorrect location.

Encryption protects GPS data during transmission but cannot verify whether the received satellite signals are genuine. Multi-constellation GNSS and sensor fusion are commonly used to detect spoofing.

### Result
Requires dedicated navigation hardware for protection.

## 3. Endpoint Compromise

The attacker gains physical or software access to the UAV or the Ground Control Station and attempts to extract keys or modify the firmware.

Once a device is compromised, encryption alone cannot protect stored secrets. Secure Boot, Hardware Security Modules (HSM), and firmware verification are required.
