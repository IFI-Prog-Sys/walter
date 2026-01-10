"""
Walter Discord Bot entrypoint.

This module configures logging, loads runtime configuration, initializes the Discord client
and application commands, and wires the bot to the Walter backend for managing Minecraft
whitelist entries via a slash command.

Environment variables required:
- WALTER_DISCORD_KEY: Discord bot token
- WALTER_GUILD_ID: Target guild (server) ID where commands are registered

Configuration file:
- config.yaml in the working directory, expected to contain:
  paths:
    discord_database: <path to discord DB>
  rcon_secret: <secret>

▗▄▄▖  ▗▄▖ ▗▖ ▗▖▗▄▄▄▖▗▄▄▖ ▗▄▄▄▖▗▄▄▄
▐▌ ▐▌▐▌ ▐▌▐▌ ▐▌▐▌   ▐▌ ▐▌▐▌   ▐▌  █
▐▛▀▘ ▐▌ ▐▌▐▌ ▐▌▐▛▀▀▘▐▛▀▚▖▐▛▀▀▘▐▌  █
▐▌   ▝▚▄▞▘▐▙█▟▌▐▙▄▄▖▐▌ ▐▌▐▙▄▄▖▐▙▄▄▀
▗▄▄▖▗▖  ▗▖
▐▌ ▐▌▝▚▞▘
▐▛▀▚▖ ▐▌
▐▙▄▞▘ ▐▌
▗▄▄▄▖▗▖  ▗▖ ▗▄▄▖▗▄▄▖ ▗▄▄▖ ▗▄▄▄▖ ▗▄▄▖ ▗▄▄▖ ▗▄▖
▐▌   ▐▌  ▐▌▐▌   ▐▌ ▐▌▐▌ ▐▌▐▌   ▐▌   ▐▌   ▐▌ ▐▌
▐▛▀▀▘▐▌  ▐▌ ▝▀▚▖▐▛▀▘ ▐▛▀▚▖▐▛▀▀▘ ▝▀▚▖ ▝▀▚▖▐▌ ▐▌
▐▙▄▄▖ ▝▚▞▘ ▗▄▄▞▘▐▌   ▐▌ ▐▌▐▙▄▄▖▗▄▄▞▘▗▄▄▞▘▝▚▄▞▘
"""

import logging
import sys
from os import environ
import discord
from discord import app_commands
import yaml
from walter import Walter, WalterStatus

logger = logging.getLogger("Walter.Main")
logger.setLevel(logging.DEBUG)

# systemd already tracks date and time so the redundancy is unnecessary
logger_formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")

handler_info = logging.StreamHandler(sys.stdout)
handler_info.setLevel(logging.INFO)
handler_info.addFilter(lambda r: r.levelno < logging.ERROR)  # keep stdout to < ERROR
handler_info.setFormatter(logger_formatter)

handler_error = logging.StreamHandler(sys.stderr)
handler_error.setLevel(logging.ERROR)
handler_error.setFormatter(logger_formatter)

logger.addHandler(handler_info)
logger.addHandler(handler_error)


def load_config() -> dict:
    """
    Load and validate configuration from config.yaml.

    Reads config.yaml from the working directory, parses it as YAML, and ensures the
    top-level structure is a dictionary.

    Returns:
        dict: The parsed configuration mapping.

    Raises:
        SystemExit: If the file contains malformed YAML or the structure is unexpected,
                    or if there are I/O issues. In these cases, an error is logged
                    and the process exits with status code 1.

    Notes:
        - This function assumes config.yaml exists in the current working directory.
        - Expected keys (validated elsewhere): "paths.discord_database",
          "rcon_secret".
    """
    try:
        with open("config.yaml", "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
            if isinstance(config, dict):
                return config
            raise Exception
    except yaml.YAMLError:
        logger.error("Malformed config.yaml file. Could not load.")
        sys.exit(1)
    except Exception:
        logger.error("Unexpected behaviour when trying to load config")
        sys.exit(1)


def main():
    """
    Entrypoint for the Walter Discord bot.

    Workflow:
    1. Load configuration via load_config() (database paths, RCON secret).
    2. Read required environment variables:
       - WALTER_DISCORD_KEY (bot token)
       - WALTER_GUILD_ID (target guild/server ID)
    3. Initialize the Discord client and the application command tree.
    4. Instantiate the Walter backend with configured paths and secrets.
    5. Register the /whitelist command and the on_ready event handler.
    6. Run the Discord client.

    Side Effects:
        - Logs startup and error messages.
        - Syncs application commands to the specified guild on ready.
        - Sets the bot presence to guide users to use /whitelist.
        - Exits the process with status 1 if required environment variables
          are missing.

    Notes:
        Ensure:
        - The bot has permissions to create slash commands in the target guild.
        - Environment variables WALTER_DISCORD_KEY and WALTER_GUILD_ID are set.
        - config.yaml exists with the expected structure and keys.
    """
    config = load_config()
    discord_database_path = config["paths"]["discord_database"]
    # admin_uid = config["admin_uid"]
    rcon_secret = config["rcon_secret"]

    token, guild_id = environ.get("WALTER_DISCORD_KEY"), environ.get("WALTER_GUILD_ID")
    if not token:
        logger.error("Couldn't get Discord API token from env vars")
        sys.exit(1)
    elif not guild_id:
        logger.error("Couldn't get Guild ID from env vars")
        sys.exit(1)

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    walter = Walter(discord_database_path, rcon_secret)

    @tree.command(
        name="whitelist",
        description="Add yourself to the minecraft server whitelist",
        guild=discord.Object(id=guild_id),
    )
    async def whitelist(interaction, minecraft_username: str):
        """
        Add a Minecraft username to the server whitelist via a slash command.

        Parameters:
            interaction (discord.Interaction): The Discord interaction context.
            minecraft_username (str): The Minecraft username to whitelist.

        Behavior:
            - Resolves the invoking Discord user name.
            - Delegates to Walter.add_to_whitelist(discord_username, minecraft_username).
            - Sends a localized response based on the returned status:
              - WalterStatus.DISCORD_ALREADY_USED: User has already consumed their whitelist token.
              - WalterStatus.ALREADY_WHITELISTED: User is already whitelisted.
              - Otherwise: Success response indicating whitelist update may take ~30 seconds.

        Responses:
            Sends one message to the invoking user describing the outcome.
        """
        discord_username = str(interaction.user)
        status_code = walter.add_to_whitelist(discord_username, minecraft_username)

        if status_code == WalterStatus.DISCORD_ALREADY_USED:
            await interaction.response.send_message(
                ":red_square: :orange_book: :red_square:\nOops, det virker som om du allerede har brukt din whitelist token! Vennligst ta kontakt med en @server_admin om du mener det har oppstått en feil, eller om du vil whiteliste noen andre."
            )
        elif status_code == WalterStatus.ALREADY_WHITELISTED:
            await interaction.response.send_message(
                ":yellow_square::grey_question::yellow_square:\n Oops, det virker som om du allerede har blitt whitelistet på serveren.\nVennligst ta kontakt med en @server_admin om du mener det har oppstått en feil"
            )
        else:
            await interaction.response.send_message(
                f":green_circle: :book: :green_circle:\n{minecraft_username} har blitt lagt til whitelisten! Vennligst vent 30 sekunder sånn at whitelist oppdateringen kan vedtas.\nGood luck, have fun!"
            )

    @client.event
    async def on_ready():
        """
        Fired when the Discord client has connected and is ready.

        Actions:
            - Syncs application commands to the configured guild.
            - Sets the bot presence to “listening” with a hint for using /whitelist.
            - Logs a startup banner to indicate the bot is operational.

        Purpose:
            Ensures the slash command is registered and users see a helpful status
            indicating how to invoke the whitelist command.
        """
        await tree.sync(guild=discord.Object(id=guild_id))

        # Courtesy of https://stackoverflow.com/a/70644609
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                name="/whitelist {minecraft_username}",
                type=discord.ActivityType.listening,
            ),
        )

        logger.info("Good morning, Walter is fully awake!")

    client.run(token)


if __name__ == "__main__":
    main()
