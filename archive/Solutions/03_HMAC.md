# **HMAC with SHA-256**

# **Objective**

The third solution we considered was implementing **HMAC with SHA-256** to ensure the **integrity** and **authenticity** of MAVLink messages during communication between the **Ground Control Station (GCS)** and the **UAV**.

 
# **Why We Considered HMAC with SHA-256**

After evaluating the **Affine Cipher**, we realized that although it provided basic encryption, it could not verify whether a received message had been modified during transmission.

We selected **HMAC with SHA-256** because it is a widely used cryptographic mechanism that:

- Verifies the authenticity of the sender.
- Ensures message integrity.
- Detects any unauthorized modification of transmitted data.
- Uses a secure shared secret key.

# **Our Approach**

Before transmitting a MAVLink message, an **HMAC** was generated using the **SHA-256** hashing algorithm and a shared secret key. The generated HMAC was transmitted along with the MAVLink packet.
Upon receiving the message, the UAV recalculated the HMAC using the same shared secret key. If both HMAC values matched, the message was accepted; otherwise, it was discarded.

# **Result**

IT successfully verified the integrity and authenticity of MAVLink messages.
Any packet modified during transmission resulted in an HMAC mismatch and was immediately rejected.
However, although HMAC protected message integrity, the original MAVLink payload was still transmitted in **plaintext**.

# **Limitations**

- Does **not encrypt** MAVLink messages.
- Does **not provide message confidentiality**.

# **Conclusion**

Although **HMAC with SHA-256** successfully provided **message integrity** and **authentication**, it could not ensure **confidentiality** because the MAVLink messages remained unencrypted.

So HMAC with SHA-256 alone was insufficient.
