# Simple Chat

#### Portfolio Project

A simple CLI-based chat application that allows anyone to host and join a chat server.

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

# Extra

Use:

```text
/help
```

to view all available chat commands.

---

# Privacy and Tunneling

The app does not show client IP addresses in the chat, host logs, or `/see_users`.
The host still receives network connections at the operating system level, so use a
tunnel if you do not want players to connect directly to the host machine.

## Hide the Host IP with playit.gg

1. Start the chat server first. By default it listens on port `6667`.
2. Install and open the playit.gg agent from https://playit.gg/.
3. Create a tunnel for a TCP service.
4. Set the local address/port in playit to your chat server:

```text
127.0.0.1:PORT
```

5. playit will give you a public address, usually a hostname plus port.
6. Give users only the playit address, not your home IP.
7. Clients connect with:

```text
/connect PLAYIT_ADDRESS:PLAYIT_PORT
```

Tunnel URLs with a TCP scheme also work, for example:

```text
/connect tcp://nnqds-157-100-87-219.run.pinggy-free.link:35561
```

If you change the chat port in `Scripts/config/config.json`, use the same port in
the playit tunnel.

Optional: put the playit address in `share_address` inside
`Scripts/config/config.json`. Then the host can run `/host` to print the tunnel
address instead of a local IP.
