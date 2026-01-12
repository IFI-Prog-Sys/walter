"""
Walter Discord Bot entrypoint.

This module configures logging, loads runtime configuration, initializes the Discord client
and application commands, and wires the bot to the Walter backend for managing Minecraft
whitelist entries via a slash command.

Environment variables required:
- WALTER_DISCORD_KEY: Discord bot token
- WALTER_RCON_SECRET: RCON secret for the Minecraft server

Configuration file:
- config.yaml in the working directory, expected to contain:
  paths:
    discord_database: <path to discord DB>
  guild_id: Target guild (server) ID where commands are registered

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
from dataclasses import dataclass
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


@dataclass
class WalterConfig:
    discord_token: str
    guild_id: int
    discord_database_path: str
    rcon_secret: str


def load_config() -> WalterConfig:
    """
    Load and validate configuration from config.yaml and environment variables.

    Reads config.yaml for database paths and guild ID.
    Reads environment variables for secrets.

    Returns:
        WalterConfig: The parsed and validated configuration.

    Raises:
        SystemExit: If the file contains malformed YAML, is missing keys, or
                    if required environment variables are unset. In these cases,
                    an error is logged and the process exits with status code 1.

    Notes:
        - This function assumes config.yaml exists in the current working directory.
        - Requires 'paths.discord_database' and 'guild_id' in config.yaml.
        - Requires 'WALTER_DISCORD_KEY' and 'WALTER_RCON_SECRET' in environment.
    """
    # Load YAML
    try:
        with open("config.yaml", "r", encoding="utf-8") as file:
            config_yaml = yaml.safe_load(file)
            if not isinstance(config_yaml, dict):
                logger.error("Config root must be a dictionary")
                sys.exit(1)
    except (yaml.YAMLError, IOError) as e:
        logger.error(f"Could not load config.yaml: {e}")
        sys.exit(1)

    # Extract and validate values
    paths = config_yaml.get("paths", {})
    discord_database_path = paths.get("discord_database")
    if not discord_database_path:
        logger.error("Missing 'paths.discord_database' in config.yaml")
        sys.exit(1)

    raw_guild_id = config_yaml.get("guild_id")
    if raw_guild_id is None:
        logger.error("Missing 'guild_id' in config.yaml")
        sys.exit(1)
    
    try:
        guild_id = int(raw_guild_id)
    except ValueError:
        logger.error("Invalid 'guild_id' in config.yaml; must be an integer")
        sys.exit(1)

    token = environ.get("WALTER_DISCORD_KEY")
    if not token:
        logger.error("Couldn't get Discord API token from env vars (WALTER_DISCORD_KEY)")
        sys.exit(1)

    rcon_secret = environ.get("WALTER_RCON_SECRET")
    if not rcon_secret:
        logger.error("Couldn't get RCON secret from env vars (WALTER_RCON_SECRET)")
        sys.exit(1)

    return WalterConfig(
        discord_token=token,
        guild_id=guild_id,
        discord_database_path=discord_database_path,
        rcon_secret=rcon_secret
    )


def main():
    """
    Entrypoint for the Walter Discord bot.

    Workflow:
    1. Load configuration via load_config().
    2. Initialize the Discord client and the application command tree.
    3. Instantiate the Walter backend with configured paths and secrets.
    4. Register the /whitelist command and the on_ready event handler.
    5. Run the Discord client.

    Side Effects:
        - Logs startup and error messages.
        - Syncs application commands to the specified guild on ready.
        - Sets the bot presence to guide users to use /whitelist.
        - Exits the process with status 1 if configuration is invalid.
    """
    config = load_config()

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    walter = Walter(config.discord_database_path, config.rcon_secret)

    @tree.command(
        name="whitelist",
        description="Add yourself to the minecraft server whitelist",
        guild=discord.Object(id=config.guild_id),
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
        await tree.sync(guild=discord.Object(id=config.guild_id))

        # Courtesy of https://stackoverflow.com/a/70644609
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                name="/whitelist {minecraft_username}",
                type=discord.ActivityType.listening,
            ),
        )

        logger.info("Good morning, Walter is fully awake!")

    client.run(config.discord_token)


if __name__ == "__main__":
    main()
