import logging
import sys
import signal
from enum import Enum
import requests
from mcrcon import MCRcon

"""
Walter backend for managing Minecraft whitelisting.

This module encapsulates the logic for:
- Tracking which Discord users have consumed their whitelist token.
- Tracking which Minecraft players are already whitelisted.
- Validating Minecraft usernames against Mojang's API.
- Interacting with a local Minecraft server via RCON to add players to the whitelist.
- Persisting the above state to simple space-delimited files.

Logging:
- INFO: Operational messages (databases loaded, RCON responses).
- ERROR: Failures (I/O errors, network validation errors).

Signals:
- SIGINT, SIGTERM: Trigger clean RCON disconnect and process exit.
"""

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
        - Tracks and persists which Discord users have used their whitelist token.
        - Tracks and persists which Minecraft players are already whitelisted.
        - Handles SIGINT/SIGTERM to gracefully close RCON before exiting.

    Parameters:
        path_to_discord_database (str): Path to the file tracking Discord users
            who have consumed their whitelist token. Space-delimited usernames.
        path_to_minecraft_database (str): Path to the file tracking already
            whitelisted Minecraft player names. Space-delimited usernames.
        rcon_secret (str): RCON password used to authenticate to the local server.

    Notes:
        - RCON is initialized against 127.0.0.1 using the provided secret.
        - Files are read at initialization and written back when state changes.
        - Signal handlers are registered for SIGINT and SIGTERM.
    """
    def __init__(
        self,
        path_to_discord_database: str,
        path_to_minecraft_database: str,
        rcon_secret: str,
    ):
        self.rcon_socket = MCRcon("127.0.0.1", rcon_secret)
        self.rcon_socket.connect()

        self._already_used: set[str] = self.recall_who_used(path_to_discord_database)
        logger.info("Loaded Discord database")

        self._already_whitelisted: set[str] = self.recall_who_used(
            path_to_minecraft_database
        )
        logger.info("Loaded Minecraft database")

        self._path_to_discord_database: str = path_to_discord_database
        self._path_to_minecraft_database: str = path_to_minecraft_database

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_close)

    def _signal_close(self, signum, frame):
        """
        Signal handler to gracefully disconnect RCON and exit.

        Actions:
            - Logs the received signal.
            - Disconnects the RCON socket.
            - Restores default handling for the received signal.
            - Raises KeyboardInterrupt on SIGINT or SystemExit on SIGTERM to exit.

        Parameters:
            signum (int): The signal number received (e.g., SIGINT, SIGTERM).
            frame: The current stack frame (unused).

        Side Effects:
            - Disconnects RCON.
            - Terminates the process via exception to allow upstream handling.
        """
        logger.info("Received signal %s; closing RCON and exiting.", signum)
        self.rcon_socket.disconnect()
        signal.signal(signum, signal.SIG_DFL)
        raise KeyboardInterrupt if signum == signal.SIGINT else SystemExit

    def recall_who_used(self, path_to_file: str) -> set[str]:
        """
        Load a set of usernames from a space-delimited file.

        Parameters:
            path_to_file (str): Path to the file to read.

        Returns:
            set[str]: A set of strings parsed from the file. Empty strings are
                      ignored if present due to strip/split behavior.

        Raises:
            FileNotFoundError, OSError: If the file cannot be opened.
            UnicodeDecodeError: If the file cannot be decoded as UTF-8.

        Notes:
            - The file is expected to contain usernames separated by whitespace.
        """
        with open(path_to_file, "r", encoding="utf-8") as file:
            return set(file.read().strip().split())

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

    def __add_player_to_whitelist(self, player_name: str):
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

    def add_to_whitelist(
        self, discord_username: str, player_name: str
    ) -> WalterStatus:  # returns 0 if sucess, returns 1 if issue
        """
        Add a Minecraft player to the whitelist, enforcing per-Discord-user limits.

        Workflow:
            1. Check if the Discord user has already used their whitelist token.
            2. Check if the Minecraft player is already whitelisted.
            3. Validate the Minecraft username via Mojang API.
            4. Add the player via RCON if valid and not already present.
            5. Persist updated state to disk for both Discord and Minecraft databases.

        Parameters:
            discord_username (str): The invoking Discord user's name (or identifier).
            player_name (str): The Minecraft username to add to the whitelist.

        Returns:
            WalterStatus:
                - DISCORD_ALREADY_USED: The Discord user has already consumed their token.
                - ALREADY_WHITELISTED: The player is already whitelisted.
                - MINECRAFT_USER_NOT_VALID: Username validation failed.
                - OK: Successfully whitelisted and state persisted.

        Side Effects:
            - Writes to the Discord and Minecraft username database files.
            - Sends an RCON command to the server.

        Notes:
            - Persistence uses space-delimited files and overwrites the entire file.
        """
        if discord_username in self._already_used:
            return WalterStatus.DISCORD_ALREADY_USED
        if player_name in self._already_whitelisted:
            return WalterStatus.ALREADY_WHITELISTED

        valid = self.__check_minecraft_user_is_valid(player_name)

        if not valid:
            return WalterStatus.MINECRAFT_USER_NOT_VALID

        self.__add_player_to_whitelist(player_name)

        self._already_used.add(discord_username)
        self.__write_to_username_database(
            self._path_to_discord_database, self._already_used
        )

        self._already_whitelisted.add(player_name)
        self.__write_to_username_database(
            self._path_to_minecraft_database, self._already_whitelisted
        )

        return WalterStatus.OK

    def __write_to_username_database(self, path_to_database, names):
        """
        Persist a set of usernames to a space-delimited file.

        Parameters:
            path_to_database (str): Path to the output file to write.
            names (set[str] | Iterable[str]): Collection of usernames to write.

        Side Effects:
            - Overwrites the target file with usernames separated by single spaces.

        Raises:
            Logs ERROR on any exception encountered during write.

        Notes:
            - The order of names in the file is arbitrary due to set iteration.
        """
        try:
            with open(path_to_database, "w", encoding="utf-8") as file:
                file.write(" ".join(names))
        except Exception as e:
            logger.error("Error writing to username database: %s", e)
