# Walter The Whitelister
Prog.Sys();'s one and only Minecraft whitelist management bot

## Basic Overview
Walter is essentially a specialised JSON editor that, upon request, modifies the Minecraft server whitelist.json.

The bot comes in two parts; The sytemd service and the datapack.
The systemd service runds the main.py file in the background, makes the necesarry edits to the whitelist.json file.
The datapack forces the server to acknowledge these updates by reloading the whitelist table every 15 s.

## File structure
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
