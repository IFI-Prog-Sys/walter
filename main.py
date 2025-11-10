import discord
from discord import app_commands
from walter import *
import json

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


def extract_secrets(path_to_secrets: str):
    with open(path_to_secrets, 'r') as file:
        data = json.load(file)

    token = data.get('token')
    guild_id = data.get('guild_id')

    return token, guild_id

def main():
    TOKEN, GUILD_ID = extract_secrets("./data/secrets.json")
    DISCORD_DATABASE_PATH = "./data/discord_database"
    MINECRAFT_DATABASE_PATH = "./data/minecraft_database"
    WHITELIST_PATH = "./data/whitelist.json"

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    walter = Walter(DISCORD_DATABASE_PATH, WHITELIST_PATH, MINECRAFT_DATABASE_PATH)

    @tree.command(
    name="whitelist",
    description="Add yourself to the minecraft server whitelist",
    guild=discord.Object(id=GUILD_ID)
    )

    async def whitelist(interaction, minecraft_username: str):
        discord_username = str(interaction.user)
        status_code = walter.add_to_whitelist(discord_username, minecraft_username)
        
        if status_code == 1: # Status code 1 is an erorr
            await interaction.response.send_message(":red_square: :orange_book: :red_square:\nOops, det virker som om du allerede har brukt din whitelist token! Vennligst ta kontakt med en @’server_admin om du mener det har oppstått en feil, eller om du vil whiteliste noen andre.")
        elif status_code == 2:
            await interaction.response.send_message(":yellow_square::grey_question::yellow_square:\n Oops, det virker som om du allerede har blitt whitelistet på serveren.\nVennligst ta kontakt med en @’server_admin om du mener det har oppstått en feil")
        else:
            await interaction.response.send_message(f":green_circle: :book: :green_circle:\n{minecraft_username} har blitt lagt til whitelisten! Vennligst vent 30 sekunder sånn at whitelist oppdateringen kan vedtas.\nGood luck, have fun!")


    @client.event
    async def on_ready():
        await tree.sync(guild=discord.Object(id=GUILD_ID))

        # Courtesy of https://stackoverflow.com/a/70644609
        await client.change_presence(status=discord.Status.online,
                activity=discord.Activity(name="/whitelist {minecraft_username}", type=discord.ActivityType.listening))

        print("\n"+"-"*10+"Good morning, Walter is fully awake!"+"-"*10+"\n")

    client.run(TOKEN)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupt detected")
        exit(0)

