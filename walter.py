import json
from requests import get

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


class Walter:

    def __init__(self, path_to_discord_database:str , path_to_server_whitelist: str, path_to_minecraft_database):
        self._already_used: list = self.recall_who_used(path_to_discord_database)

        print("\nLoaded Discord database!")
        print()

        self._already_whitelisted: list = self.recall_who_used(path_to_minecraft_database)

        print("\nLoaded Minecraft database!")
        print()

        self._path_to_whitelist: str = path_to_server_whitelist
        self._path_to_discord_database: str = path_to_discord_database
        self._path_to_minecraft_database: str = path_to_minecraft_database

    def recall_who_used(self, path_to_file: str) -> list[str]:
        with open(path_to_file, 'r') as file:
            return file.read().strip().split()

    def __write_to_whitelist(self, player_name: str, uuid: str) -> int:
        with open(self._path_to_whitelist, 'r') as file:
            data = json.load(file)

        new_entry = {
                "uuid": uuid,
                "name": player_name
        }

        data.append(new_entry)

        with open(self._path_to_whitelist, 'w') as file:
            json.dump(data, file, indent=4)

        return 0

    def __query_uuid(self, username: str) -> str: # returns UUID
        # Thank you to https://stackoverflow.com/a/63096501
        url = f"https://api.mojang.com/users/profiles/minecraft/{username}?"
        response = get(url)
        raw_uuid = response.json()["id"]

        part1 = raw_uuid[:8]
        part2 = raw_uuid[8:12]
        part3 = raw_uuid[12:16]
        part4 = raw_uuid[16:20]
        part5 = raw_uuid[20:]
        
        uuid = f"{part1}-{part2}-{part3}-{part4}-{part5}"

        return uuid

    def add_to_whitelist(self, discord_username: str, player_name: str) -> int: # returns 0 if sucess, returns 1 if issue
        if (discord_username in self._already_used):
            return 1

        elif (player_name in self._already_whitelisted):
            return 2

        uuid = self.__query_uuid(player_name)
        self.__write_to_whitelist(player_name, uuid)

        self._already_used.append(discord_username)
        self.__write_to_username_database(self._path_to_discord_database, self._already_used)

        self._already_whitelisted.append(player_name)
        self.__write_to_username_database(self._path_to_minecraft_database, self._already_whitelisted)
        
        return 0

    def __write_to_username_database(self, path_to_database, path_to_list):
        try:
            with open(path_to_database, 'w') as file:
                file.write(" ".join(path_to_list))
        except:
            print("Error writing to username database")
            return
