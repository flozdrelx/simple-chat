# Hexium Chat

#### Portfolio Project

A self-hosted GUI chat application focused on privacy, customization, and direct peer-to-peer style communication.

---

# How to Use

## Windows

Before starting, make sure Python is installed on your system.

### Start the Server

1. Open the `RunServer` folder
2. Double click `run.bat`
3. Wait until the server starts

### Start the Client

1. Open the `RunClient` folder
2. Double click `run.bat`
3. Wait until the client starts

You can now test the chat application.

---

## Linux / macOS

Before starting, make sure Python is installed on your system.

### Start the Server

1. Open a terminal inside the `RunServer` folder
2. Make the script executable:

```bash
chmod +x run.sh
```

3. Run the script:

```bash
./run.sh
```

### Start the Client

1. Open a terminal inside the `RunClient` folder
2. Make the script executable:

```bash
chmod +x run.sh
```

3. Run the script:

```bash
./run.sh
```

You can now test the chat application.

---

# Current Features

* Users can host their own chat server
* Multiple users can connect and chat in real time
* Hosts can participate in the chat
* Basic chat commands
* Host moderation commands
* Host client manager with connection UUIDs and one-click kicking
* TCP tunneling support
* Graphical User Interface (GUI)
* Room password support
* End-to-end encrypted text and PNG/JPG/WEBP image sharing
* Open source and self-hosted architecture

---

# Commands

Use:

```text
/help
```

to view all available chat commands.

Hosts can toggle image sharing with `/allowimgs` and configure the per-user
images-per-minute limit with `/imglimit <count>` (default: 5). GUI users can
use the Image button; terminal users can use `/image <path>`.

Hosts can manage active connections from the GUI's **Clients** tab. Each
connection has a numeric session ID and a UUID. `/see_users` lists both, and
`/kick <id|uuid>` accepts either a numeric ID or a unique UUID prefix.

Images are decoded and re-saved with Pillow before transmission, removing EXIF
and other source metadata. Files larger than 5 MB are recompressed and resized
when necessary; SVG and formats other than PNG, JPG, and WEBP are rejected.

Install dependencies before starting:

```bash
python -m pip install -r requirements.txt
python -m pip install ./rust-crypto
```

The second command builds the Rust crypto extension. It requires the stable
Rust toolchain (including Cargo). The application refuses to start if this
module is absent; there is no plaintext fallback.

## End-to-end encryption

Each installation creates a local X25519 identity at
`~/.hexium-chat/identity.key`. Only its public key is registered with the room.
For each recipient, the Rust module derives a distinct session key with
X25519 and HKDF-SHA256, then authenticates and encrypts the text or sanitized
image bytes using XChaCha20-Poly1305 and a fresh 192-bit OS-random nonce.

Group messages use a per-recipient envelope. The host is a normal room
participant and receives its own encrypted recipient box, allowing one client
to chat directly with the host without requiring a second client. The host
decrypts that box locally while relaying the original envelope unchanged to
other clients. Host-authored messages are likewise encrypted for every
connected client.
Private keys and derived keys never enter protocol frames or logs. A failed
authentication check produces a generic client error and the payload is
discarded.

The client shows its public-key fingerprint after connecting. Compare
fingerprints with contacts over a separate trusted channel when protection
against an actively malicious relay is required; room passwords and transport
encryption alone do not authenticate first contact.

Run the crypto and packet tests with:

```bash
cargo test --manifest-path rust-crypto/Cargo.toml
python -m unittest discover -s tests
```

---

# Privacy and Security

Since this project is open source, both hosts and clients may run modified versions of the application.  
For safer public usage and additional privacy, consider the following recommendations.

---

# 1. Use a TCP Tunneling Service (Recommended for Hosts)

Hexium Chat supports TCP tunneling services such as Pinggy.

Instead of sharing your public IP address directly, you can create a tunnel that forwards traffic to your local chat server.

## Example

A tunneling service may generate an address similar to:

```text
tcp://example-tunnel.a.free.pinggy.link:35576
```

Clients can connect using the generated tunnel address instead of the host's public IP address.

### Benefits

- Reduces direct exposure of the host IP address
- Easier room sharing
- Adds an additional privacy layer for public sessions

## Configuration

1. Create a TCP tunnel pointing to your localhost port
2. Make sure the selected port matches the one configured in:

```text
config.json
```

3. Share the generated tunnel address only with trusted users

---

# 2. Use Room Passwords

If you are hosting a public or semi-public room, consider enabling a password.

## Example

```text
/set_pswd <password>
```

### Benefits

- Prevents unknown users from joining the room
- Adds a simple access control layer
- Useful for private sessions

### Important

Only share the password with users you trust.

---

# 3. Optional VPN Usage

Both hosts and clients may optionally use a VPN for additional privacy.

A VPN may help reduce exposure of:

- Public IP addresses
- Approximate location information
- Network-related metadata

### Note

Depending on the provider and network conditions, VPNs and tunneling services may increase latency.

---

# General Recommendations

For the best and safest experience:

- Use the official source code from the repository
- Avoid downloading untrusted modified builds
- Use passwords for private rooms
- Use a tunneling service when hosting public sessions
- Share room access only with trusted users