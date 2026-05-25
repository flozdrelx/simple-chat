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
* TCP tunneling support
* Graphical User Interface (GUI)
* Room password support
* Open source and self-hosted architecture

---

# Planned Features

* Encrypted message traffic
* Improved privacy and security systems
* Additional networking improvements using C/C++
* Redesigned GUI inspired by the Hexium aesthetic
* Better customization and room management

---

# Commands

Use:

```text
/help
```

to view all available chat commands.

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
