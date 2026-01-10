# Walter The Whitelister

Prog.Sys();'s one and only Minecraft whitelist management bot.

## About

Walter is a Python-based Discord bot that allows users to add their Minecraft username to a server's whitelist using a simple slash command.

It works by:
1.  Listening for the `/whitelist` command on a Discord server.
2.  Validating the provided Minecraft username against the official Mojang API.
3.  Using RCON to send a `whitelist add` command to the Minecraft server.
4.  Tracking which Discord user has used their "whitelist token" in a local SQLite database to prevent abuse.

The bot is designed to run as a background service using systemd.

## File Structure

```
walter/
├── config.yaml
├── LICENSE
├── main.py
├── README.md
├── requirements.txt
├── walter.py
└── walter.service
```
**Note:** The `discord_database.db` file will be created in the root directory after the first run, as specified in `config.yaml`.

## Setup and Installation

**Note:** Walter has been tested on Python 3.9. It is recommended to use a similar version.

### 1. Prerequisites
- A Minecraft server with RCON enabled.
- A Discord account with permissions to create applications.

### 2. Install Dependencies
Install the required Python packages using pip:
```bash
pip install -r requirements.txt
```

### 3. Configure Your Minecraft Server
In your Minecraft server's directory, edit the `server.properties` file and set the following values:
```properties
enable-rcon=true
rcon.password=YOUR_RCON_PASSWORD_HERE
```
Make sure the `rcon.port` (default: 25575) is not blocked by a firewall. Restart your Minecraft server for the changes to take effect.

### 4. Create a Discord Bot
1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2.  In the "Bot" tab, create a bot user and copy its **token**.
3.  You will also need the **Server ID** (Guild ID) of the Discord server you want to add the bot to. You can get this by enabling Developer Mode in Discord, right-clicking your server icon, and selecting "Copy Server ID".

### 5. Configure Walter
1.  **Edit `config.yaml`:**
    -   `rcon_secret`: Set this to the RCON password you chose in `server.properties`.
    -   The other settings can typically be left as default.

2.  **Set Environment Variables:**
    The bot requires two environment variables to authenticate with Discord.
    -   `WALTER_DISCORD_KEY`: Your Discord application's bot token.
    -   `WALTER_GUILD_ID`: The ID of your Discord server (guild).

    You can set these permanently by adding the following lines to your shell's profile (e.g., `~/.bash_profile` or `~/.zshrc`), then running `source ~/.bash_profile` or opening a new terminal.
    ```bash
    export WALTER_DISCORD_KEY="YOUR_DISCORD_BOT_TOKEN"
    export WALTER_GUILD_ID="YOUR_DISCORD_SERVER_ID"
    ```

### 6. Invite the Bot to Your Server
Invite your new Discord application to your server.

The bot requires the following permissions:
- View Channels
- Send Messages
- Send Messages in Threads
- Read Message History

## Running the Bot

You can run the bot directly for testing or as a systemd service for production.

### Running Directly
To run the bot in the foreground for testing or development:
```bash
python main.py
```

### Running as a systemd Service (Recommended)
This ensures the bot runs in the background and restarts automatically.

1.  **Edit `walter.service`:**
    Replace the placeholder paths for `ExecStart` and `WorkingDirectory` with the **absolute paths** to your project files. You must also set the `WALTER_DISCORD_KEY` and `WALTER_GUILD_ID` environment variables here.
    ```ini
    [Unit]
    Description=Walter The Whitelister

    [Service]
    ExecStart=/usr/bin/python /home/user/path/to/walter/main.py
    WorkingDirectory=/home/user/path/to/walter
    Environment=WALTER_DISCORD_KEY=your_api_key_here
    Environment=WALTER_GUILD_ID=your_guild_id_here

    [Install]
    WantedBy=default.target
    ```

2.  **Install and Start the Service:**
    Copy the service file to the systemd user directory, then start and enable it.
    ```bash
    # Create the directory if it doesn't exist
    mkdir -p ~/.config/systemd/user/

    # Copy the service file
    cp walter.service ~/.config/systemd/user/

    # Reload the systemd daemon to recognize the new service
    systemctl --user daemon-reload

    # Start the service
    systemctl --user start walter.service
    ```

3.  **(Optional) Enable Auto-startup:**
    To make the bot start automatically when you log in:
    ```bash
    systemctl --user enable walter.service
    ```

4.  **Check Status and Logs:**
    ```bash
    # Check the status
    systemctl --user status walter.service

    # View live logs
    journalctl --user -fu walter.service
    ```

## Usage
Once the bot is running and connected to your Discord server, users can add themselves to the whitelist with the following command:
```
/whitelist minecraft_username: <their-minecraft-username>
```

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

