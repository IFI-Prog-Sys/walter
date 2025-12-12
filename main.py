import logging
import sys
from os import environ
import discord
from discord import app_commands
import yaml
from walter import Walter

# ▗▄▄▖  ▗▄▖ ▗▖ ▗▖▗▄▄▄▖▗▄▄▖ ▗▄▄▄▖▗▄▄▄
# ▐▌ ▐▌▐▌ ▐▌▐▌ ▐▌▐▌   ▐▌ ▐▌▐▌   ▐▌  █
# ▐▛▀▘ ▐▌ ▐▌▐▌ ▐▌▐▛▀▀▘▐▛▀▚▖▐▛▀▀▘▐▌  █
# ▐▌   ▝▚▄▞▘▐▙█▟▌▐▙▄▄▖▐▌ ▐▌▐▙▄▄▖▐▙▄▄▀
# ▗▄▄▖▗▖  ▗▖
# ▐▌ ▐▌▝▚▞▘
# ▐▛▀▚▖ ▐▌
# ▐▙▄▞▘ ▐▌
# ▗▄▄▄▖▗▖  ▗▖ ▗▄▄▖▗▄▄▖ ▗▄▄▖ ▗▄▄▄▖ ▗▄▄▖ ▗▄▄▖ ▗▄▖
# ▐▌   ▐▌  ▐▌▐▌   ▐▌ ▐▌▐▌ ▐▌▐▌   ▐▌   ▐▌   ▐▌ ▐▌
# ▐▛▀▀▘▐▌  ▐▌ ▝▀▚▖▐▛▀▘ ▐▛▀▚▖▐▛▀▀▘ ▝▀▚▖ ▝▀▚▖▐▌ ▐▌
# ▐▙▄▄▖ ▝▚▞▘ ▗▄▄▞▘▐▌   ▐▌ ▐▌▐▙▄▄▖▗▄▄▞▘▗▄▄▞▘▝▚▄▞▘

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
    """Load configuration from config.yaml.

    Reads config.yaml from the working directory, parses it as YAML,
    and validates that the root is a dict.

    Returns:
        dict: Parsed configuration mapping.

    Exits:
        - On malformed YAML (logs an error and exits with status 1).
        - On unexpected structure or IO issues (logs an error and exits with status 1).
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
    """Entrypoint for the Walter Discord bot.

    Steps:
    1. Load configuration (database paths) via load_config().
    2. Read required environment variables:
       - WALTER_DISCORD_KEY (bot token)
       - WALTER_GUILD_ID (guild/server ID)
    3. Initialize Discord client and application command tree.
    4. Instantiate Walter backend with database paths.
    5. Register the /whitelist command and ready event.
    6. Start the Discord client.

    Side Effects:
        - Configures Discord presence text to indicate how to use /whitelist.
        - Syncs application commands to the specified guild on ready.
        - Prints a startup banner to stdout once ready.

    Notes:
        Ensure the bot has permissions to create slash commands in the target guild,
        and that the environment variables and config.yaml are correctly set.
    """
    config = load_config()
    DISCORD_DATABASE_PATH = config["paths"]["discord_database"]
    MINECRAFT_DATABASE_PATH = config["paths"]["minecraft_database"]

    TOKEN, GUILD_ID = environ.get("WALTER_GUILD_ID"), environ.get("WALTER_DISCORD_KEY")
    if not TOKEN:
        logger.error("Couldn't get Discord API token from env vars")
        sys.exit(1)
    elif not GUILD_ID:
        logger.error("Couldn't get Guild ID from env vars")
        sys.exit(1)

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    walter = Walter(DISCORD_DATABASE_PATH, MINECRAFT_DATABASE_PATH)

    @tree.command(
        name="whitelist",
        description="Add yourself to the minecraft server whitelist",
        guild=discord.Object(id=GUILD_ID),
    )
    async def whitelist(interaction, minecraft_username: str):
        """Slash command to add a Minecraft username to the whitelist.

        Args:
        interaction (discord.Interaction): The interaction context from Discord.
        minecraft_username (str): The Minecraft username to be whitelisted.

        Behavior:
            - Looks up the invoking Discord user.
            - Delegates to Walter.add_to_whitelist(discord_username, minecraft_username).
            - Sends a localized response based on returned status code:
              1 => Already used whitelist token (error).
              2 => Already whitelisted (info).
              else => Success message with update delay notice.
        """

        discord_username = str(interaction.user)
        status_code = walter.add_to_whitelist(discord_username, minecraft_username)

        if status_code == 1:  # Status code 1 is an erorr
            await interaction.response.send_message(
                ":red_square: :orange_book: :red_square:\nOops, det virker som om du allerede har brukt din whitelist token! Vennligst ta kontakt med en @’server_admin om du mener det har oppstått en feil, eller om du vil whiteliste noen andre."
            )
        elif status_code == 2:
            await interaction.response.send_message(
                ":yellow_square::grey_question::yellow_square:\n Oops, det virker som om du allerede har blitt whitelistet på serveren.\nVennligst ta kontakt med en @’server_admin om du mener det har oppstått en feil"
            )
        else:
            await interaction.response.send_message(
                f":green_circle: :book: :green_circle:\n{minecraft_username} har blitt lagt til whitelisten! Vennligst vent 30 sekunder sånn at whitelist oppdateringen kan vedtas.\nGood luck, have fun!"
            )

    @client.event
    async def on_ready():
        """Event handler fired when the Discord client is ready.

        Actions:
            - Syncs application commands for the configured guild.
            - Sets bot presence to guide use of /whitelist.
            - Prints a startup banner to stdout.

        This ensures the slash command is available and users see a helpful status.
        """
        await tree.sync(guild=discord.Object(id=GUILD_ID))

        # Courtesy of https://stackoverflow.com/a/70644609
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                name="/whitelist {minecraft_username}",
                type=discord.ActivityType.listening,
            ),
        )

        print(
            "\n" + "-" * 10 + "Good morning, Walter is fully awake!" + "-" * 10 + "\n"
        )

    client.run(TOKEN)


if __name__ == "__main__":
    main()
