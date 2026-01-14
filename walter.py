from datetime import datetime
import logging
import sys
import signal
from enum import Enum
import sqlite3
import requests
from mcrcon import MCRcon

"""
Walter backend for managing Minecraft whitelisting.

This module encapsulates the logic for:
- Tracking which Discord users have consumed their whitelist token using a SQLite database.
- Validating Minecraft usernames against Mojang's API.
- Interacting with a local Minecraft server via RCON to add players to the whitelist.

Logging:
- INFO: Operational messages (database loaded, RCON responses).
- ERROR: Failures (I/O errors, network validation errors).

Signals:
- SIGINT, SIGTERM: Trigger clean RCON disconnect, database connection closure, and process exit.
"""

logger = logging.getLogger("Walter.Walter")
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


class WalterStatus(Enum):
    """
    Status codes returned by Walter.add_to_whitelist().

    Members:
        OK: Operation succeeded; user and player recorded and whitelisted.
        DISCORD_ALREADY_USED: The Discord user has already used their whitelist token.
        ALREADY_WHITELISTED: The Minecraft player is already whitelisted.
        MINECRAFT_USER_NOT_VALID: The provided Minecraft username did not validate
            against the Mojang API (or validation error occurred).
    """

    OK = 0
    DISCORD_ALREADY_USED = 1
    ALREADY_WHITELISTED = 2
    MINECRAFT_USER_NOT_VALID = 3


class Walter:
    """
    Backend service for managing Minecraft server whitelisting.

    Responsibilities:
        - Connects to a local Minecraft server via RCON.
        - Validates Minecraft usernames using Mojang's public API.
        - Tracks which Discord users have used their whitelist token in a SQLite database.
        - Handles SIGINT/SIGTERM to gracefully close RCON and database connections before exiting.

    Parameters:
        path_to_discord_database (str): Path to the SQLite database file for tracking
            Discord users who have consumed their whitelist token.
        rcon_secret (str): RCON password used to authenticate to the local server.

    Notes:
        - RCON is initialized against 127.0.0.1 using the provided secret.
        - The database is connected at initialization.
        - Signal handlers are registered for SIGINT and SIGTERM for graceful shutdown.
    """

    def __init__(
        self,
        path_to_discord_database: str,
        rcon_secret: str,
    ):
        self.rcon_socket = MCRcon("127.0.0.1", rcon_secret)
        self.rcon_socket.connect()

        self._discord_database_connection = sqlite3.connect(path_to_discord_database)
        self._discord_database_cursor = self._discord_database_connection.cursor()
        logger.info("Connected to Discord database")

        result = self._discord_database_cursor.execute("SELECT * FROM sqlite_master")
        if result.fetchone() is None:
            logger.info("Discord username database was empty; Creating new table")
            self._discord_database_cursor.execute(
                "CREATE TABLE users(username, tokens, created)"
            )
            logger.info("Create Table OK")

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_close)

    def _signal_close(self, signum, frame):
        """
        Signal handler to gracefully disconnect RCON, close the database, and exit.

        Actions:
            - Logs the received signal.
            - Disconnects the RCON socket.
            - Closes the SQLite database connection.
            - Restores default handling for the received signal.
            - Raises KeyboardInterrupt on SIGINT or SystemExit on SIGTERM to exit.

        Parameters:
            signum (int): The signal number received (e.g., SIGINT, SIGTERM).
            frame: The current stack frame (unused).

        Side Effects:
            - Disconnects RCON and closes the database connection.
            - Terminates the process via exception to allow upstream handling.
        """
        logger.info("Received signal %s; closing RCON and exiting.", signum)
        self.rcon_socket.disconnect()
        self._discord_database_connection.commit()
        self._discord_database_connection.close()
        signal.signal(signum, signal.SIG_DFL)
        raise KeyboardInterrupt if signum == signal.SIGINT else SystemExit

    def __check_minecraft_user_is_valid(self, username: str) -> bool:
        """
        Validate a Minecraft username using Mojang's API.

        Performs a GET request to:
            https://api.mojang.com/users/profiles/minecraft/{username}

        Parameters:
            username (str): The Minecraft username to validate.

        Returns:
            bool:
                True if the username exists (HTTP 200).
                False if not found (non-200) or if a request error occurs.

        Logs:
            - ERROR on request exceptions with details.

        Timeout:
            - 5.0 seconds per request.

        Notes:
            - This is a best-effort validation and may fail if Mojang's API
              is temporarily unavailable.
        """
        try:
            resp = requests.get(
                f"https://api.mojang.com/users/profiles/minecraft/{username}",
                timeout=5.0,
            )
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.error("Error validating Minecraft user %s: %s", username, e)
            return False

    def __add_player_to_whitelist(self, player_name: str) -> WalterStatus:
        """
        Issue an RCON command to add a player to the Minecraft whitelist.

        Parameters:
            player_name (str): The Minecraft username to whitelist.

        Side Effects:
            - Sends '/whitelist add {player_name}' via RCON to the server.
            - Logs the RCON response at INFO level.

        Notes:
            - Assumes the RCON socket is connected and authenticated.
        """
        response = self.rcon_socket.command(f"/whitelist add {player_name}")
        logger.info("(RCON) %s", response)

        if response == "Player is already whitelisted":
            return WalterStatus.ALREADY_WHITELISTED
        return WalterStatus.OK

    def add_to_whitelist(
        self, discord_username: str, player_name: str
    ) -> WalterStatus:
        """
        Add a Minecraft player to the whitelist, enforcing a one-token-per-Discord-user limit.

        Workflow:
            1. Check if the Discord user has already used their whitelist token by querying the database.
            2. Validate the Minecraft username via Mojang's API.
            3. Attempt to add the player to the server's whitelist via RCON.
            4. If the player is successfully added, record the Discord user in the database
               to mark their token as used.

        Parameters:
            discord_username (str): The invoking Discord user's name (or identifier).
            player_name (str): The Minecraft username to add to the whitelist.

        Returns:
            WalterStatus:
                - DISCORD_ALREADY_USED: The Discord user has already consumed their token.
                - MINECRAFT_USER_NOT_VALID: Username validation failed.
                - ALREADY_WHITELISTED: The player is already on the whitelist.
                - OK: Successfully added to whitelist and user recorded in database.

        Side Effects:
            - Sends an RCON command to the Minecraft server.
            - Writes to the Discord user database if the operation is successful.
        """
        database_query_result = self._discord_database_cursor.execute(
            "SELECT username FROM users WHERE username=?", (discord_username,)
        )
        username_exists = database_query_result.fetchone() is not None
        if username_exists:
            return WalterStatus.DISCORD_ALREADY_USED

        minecraft_username_is_valid = self.__check_minecraft_user_is_valid(player_name)
        if not minecraft_username_is_valid:
            return WalterStatus.MINECRAFT_USER_NOT_VALID

        add_to_whitelist_response = self.__add_player_to_whitelist(player_name)

        if add_to_whitelist_response is WalterStatus.ALREADY_WHITELISTED:
            return add_to_whitelist_response

        self.__write_to_username_database(discord_username)

        return add_to_whitelist_response

    def __write_to_username_database(self, discord_username: str):
        """
        Records a Discord user in the database to mark their whitelist token as used.

        Parameters:
            discord_username (str): The Discord username to record.

        Side Effects:
            - Inserts a new row into the 'users' table with the username, a token count
              (currently hardcoded to 0), and the creation timestamp.
            - Commits the transaction to the database.

        Raises:
            Logs ERROR on any exception encountered during the database operation.
        """
        try:
            current_time = datetime.now().isoformat()
            self._discord_database_cursor.execute(
                "INSERT INTO users VALUES (?, ?, ?)",
                (discord_username, 0, current_time),
            )
            self._discord_database_connection.commit()
            logger.info("Added %s to database", discord_username)

        except Exception as e:
            logger.error("Error adding %s to username database: %s", discord_username, e)
