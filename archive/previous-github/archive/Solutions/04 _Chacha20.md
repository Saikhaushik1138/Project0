# **ChaCha20-Poly1305**

# **Objective**

We considered implementing **ChaCha20-Poly1305** to secure **MAVLink communication** for every transmitted message.

# **Why We Considered ChaCha20-Poly1305**

After evaluating previous solutions, we observed that none of them could adequately protect the **MAVLink communication channel**.
Since MAVLink messages are transmitted **without native encryption**, they remain vulnerable to interception, modification, and spoofing.

We selected **ChaCha20-Poly1305** because it is a modern **Authenticated Encryption with Associated Data (AEAD)** algorithm that:

- **Encrypts** MAVLink messages to ensure confidentiality.
- **Authenticates** every packet using **Poly1305**.
- Detects any unauthorized modification of messages.
- Combines **encryption and authentication** in a single operation.
- Is **lightweight, fast, and efficient**, making it suitable for UAVs with limited computational resources.


# **Our Approach**

Before transmission, each **MAVLink payload** is encrypted using **ChaCha20**. Simultaneously, **Poly1305** generates an authentication tag for the encrypted message.
At the receiver, the authentication tag is verified before decryption. If verification fails, the packet is immediately discarded, preventing the UAV from processing forged or modified messages.
In our implementation, **latitude and longitude values are incorporated into the key generation process**, making the encryption context-aware. As the UAV changes location, the generated encryption key also changes, providing an additional layer of security against replay and key reuse attacks.


# **Result**

The implementation successfully secured MAVLink communication by encrypting all transmitted messages and verifying their authenticity before processing.


# **Conclusion**

Since **ChaCha20-Poly1305** provides **confidentiality**, **integrity**, and **authentication** while maintaining high computational efficiency, we selected it as our **solution**.
WE are still searching for drawbacks in ths ides.
