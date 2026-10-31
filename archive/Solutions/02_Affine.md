# **Affine Cipher**

# **Objective**

The second solution considered was implementing an **Affine Cipher** by using the UAV's **latitude** and **longitude** as dynamic encryption keys. The goal was to make the encryption dependent on the UAV's current geographical location instead of using fixed keys.

# **Why We Considered Affine Cipher**

- Latitude and longitude values are continuously updated during flight, making them suitable as dynamic inputs for key generation.

Our idea was to use:

- **Latitude** as the multiplicative key (**a**)
- **Longitude** as the additive key (**b**)

Since the UAV continuously changes its position, the encryption keys would also change dynamically throughout the flight.

# **Our Approach**

The Affine Cipher follows the equation:

> **E(x) = (ax + b) mod m**

where:

- **a** = Latitude-derived key
- **b** = Longitude-derived key

The latitude and longitude values obtained from the UAV's GPS were converted into valid integer keys before encryption.
Every MAVLink message was encrypted using these dynamically generated keys before transmission.

# **Result**

The implementation successfully demonstrated **location-dependent encryption**, where encrypted messages changed as the UAV moved to different locations.

# **Limitations**

- Does **not provide message integrity**.
- Does **not authenticate the sender**.
- Does **not prevent replay attacks**.
- Does **not prevent Man-in-the-Middle (MITM) attacks**.

# **Conclusion**

Since it could not provide integrity, and authenticity, we rejected it as the solution.
