# Walter The Whitelister
Prog.Sys();'s one and only Minecraft whitelist management bot

## Basic Overview
Walter is a Discord bot that, upon request, adds a player to your Minecraft server's whitelist.

It works by running as a systemd service that listens for commands on Discord. When a user runs the `/whitelist` command, the bot validates their Minecraft username and uses RCON to issue a `whitelist add` command to the Minecraft server.

## File structure
**Note:** Install files are not included
```
walter/
├── data/
│   ├── discord_database
│   └── minecraft_database
├── config.yaml
├── main.py
└── walter.py
```

## Getting started
**Note:** Walter has currently been tested on Python 3.9.21 running on Oracle Linux Server release 9.6

1.  Install all the project dependencies with:
    ```bash
    $ pip install -r requirements.txt
    ```
2.  On your Minecraft server, enable RCON by editing the `server.properties` file. Set the following values:
    -   `enable-rcon=true`
    -   `rcon.password=YOUR_RCON_PASSWORD_HERE`
    -   Make sure the `rcon.port` (default 25575) is not blocked by a firewall.
    -   Restart your Minecraft server for the changes to take effect.

3.  Create an application in the Discord Developer Portal.

4.  Edit the `config.yaml` file and set `rcon_secret` to the password you chose in `server.properties`.

5.  Set the following environment variables for the user that will run the bot:
    -   `WALTER_DISCORD_KEY`: Your Discord application's bot token.
    -   `WALTER_GUILD_ID`: The ID of your Discord server (guild).
    You can set these permanently by adding `export VAR_NAME="value"` to your shell's profile (e.g., `~/.bash_profile` or `~/.profile`).

6.  Invite your new Discord application into your server with the following permissions:
    -   View Channels
    -   Send Messages and Create Posts
    -   Send Messages in Threads and Posts
    -   Read Message History
    -   Use Application Commands
    -   **Note:** There is a good chance not all these permissions are strictly speaking necessary but these are what have worked for us.

7.  Edit `walter.service` and specify the `ExecStart` path to your `main.py` and the `WorkingDirectory` to the project folder.

8.  Copy the provided `walter.service` file into `/etc/systemd/user/`.

9.  Start the service by running:
    ```bash
    $ systemctl --user start walter.service
    ```
10. *(optional)* Enable auto startup by running:
    ```bash
    $ systemctl --user enable walter.service
    ```
