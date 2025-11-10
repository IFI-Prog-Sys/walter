# Walter The Whitelister
Prog.Sys();'s one and only Minecraft whitelist management bot

## Basic Overview
Walter is essentially a specialised JSON editor that, upon request, modifies the Minecraft server whitelist.json.

The bot comes in two parts; The sytemd service and the datapack.
The systemd service runs the main.py file in the background, and makes the necessary edits to the whitelist.json file.
The datapack forces the server to acknowledge these updates by reloading the whitelist every 15 s.

## File structure
**Note:** Install files are not included
```
walter/
├── data
│   ├── discord_database
│   ├── minecraft_database
│   ├── secrets.json
│   └── whitelist.json -> /path/to/whitelist.json
├── main.py
└── walter.py
```

## Getting started
**Note:** Walter has currently been tested on Python 3.9.21 running on Oracle Linux Server release 9.6

1. Create an application in the Discord Developer Portal
2. Copy the secret application API key to the value under "token:" in /data/secrets.json
3. Copy your server's guild ID to the value under "guild\_id:" in /data/secrets.json
4. Invite your new Discord application into your server with the following permissions:
    - View Channels
    - Send Messages and Create Posts
    - Send Messages in Threads and Posts
    - Read Message History
    - Use Application Commands
    - **Note:** There is a good chance not all these permissions are strictly speaking necessary but these are what have worked for us.
5. In the /data/ directory, create a symlink called "whitelist.json" that points to your server's whitelist.json file.
6. Edit "walter.service" and specify the "ExecStart" directory and "WorkingDirectory"
7. Copy the provided walter.service file into "/etc/systemd/user/" 
8. Start the service by running
```bash
$ systemctl --user start walter.service
```
9. *(optional)* Enable auto startup by running
```bash
$ systemctl --user enable walter.service
```
10. Copy the provided  "walter\_server\_integrations" datapack into your server's /world/datapacks/ directory.
11. *(if already running)* Restart your Minecraft server to enable the new datapack
12. In your server console run:
```
> function walter_server_integrations:start
```
This command will have to be run after every server reboot to enable automatic whitelist reloading
