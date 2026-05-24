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

The application does not display client IP addresses in:
- Chat messages
- Host logs
- `/see_users`

However, the host machine still receives network connections at the operating system level.  
If you do not want users connecting directly to your public IP address, consider using a tunneling service.

---

# Hide the Host IP with Pinggy

To avoid exposing your public IP address, you can use a tunneling service such as Pinggy.

Pinggy allows you to create a public TCP tunnel that forwards traffic to your local chat server, allowing users to connect using a generated tunnel URL instead of your real IP address.