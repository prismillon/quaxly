import discord
from discord import app_commands
from discord.ext import commands

from utils import Paginator


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command()
    async def help(self, interaction: discord.Interaction):
        """show Quaxly help menu"""

        embeds = [discord.Embed(color=0x47E0FF, title="Time Trials commands")]

        embeds[-1].add_field(
            name="register user",
            value="```/register```this command is useful when you just joined your server but you are already using the bot in other servers, it will add you in the server list",
        )
        embeds[-1].add_field(
            name="remove user",
            value="```/remove_user (player)```this command is useful when someone want to be removed from the list but want to stay in the server, it will remove the user from the list (you if not provided), this command is not needed when someone leave the server, in this case the user is automatically removed",
        )
        embeds[-1].add_field(
            name="save time",
            value="```/save_time items track time```this command save a time for Mario Kart World, if your time is better than the previous one it will override it, if not a confirmation prompt will be showed if you still want to override (you will be registered in the server if you were not already)",
            inline=False,
        )
        embeds[-1].add_field(
            name="delete time",
            value="```/delete_time items track```this command delete times for the specified items and track combination, this command always shows a confirmation prompt with all the times that are going to be removed",
        )
        embeds[-1].add_field(
            name="display time",
            value="```/display_time items (track) (player)```this command show times from users that are registered in the server, track and player are optional, if you do not provide any it will show the best time on each track and who owns it, if track is selected it will show the ranking on the track, if player is selected it will show the user times or the users in the role",
            inline=False,
        )

        embeds.append(discord.Embed(color=0x47E0FF, title="MK8DX Time Trials commands"))

        embeds[-1].add_field(
            name="dx save time",
            value="```/dx save_time speed items track time```this command save a time for Mario Kart 8 Deluxe, if your time is better than the previous one it will override it, if not a confirmation prompt will be showed if you still want to override (you will be registered in the server if you were not already)",
            inline=False,
        )
        embeds[-1].add_field(
            name="dx delete time",
            value="```/dx delete_time speed items (track)```this command delete times for MK8DX, if track is not provided it will delete all times for the specified speed and items combination, this command always shows a confirmation prompt with all the times that are going to be removed",
        )
        embeds[-1].add_field(
            name="dx display time",
            value="```/dx display_time speed items (track) (player)```this command show MK8DX times from users that are registered in the server, track and player are optional, if you do not provide any it will show the best time on each track and who owns it, if track is selected it will show the ranking on the track, if player is selected it will show the user times or the users in the role",
            inline=False,
        )
        embeds[-1].add_field(
            name="dx import time",
            value="```/dx import_time speed items (name)```this command imports times from Cadoizzob bot for MK8DX, name is optional and defaults to your display name, make sure your name matches the one in Cadoizzob",
            inline=False,
        )

        embeds.append(discord.Embed(color=0x47E0FF, title="Lounge commands"))

        embeds[-1].add_field(
            name="role stats",
            value="```/role_stats role (stat) (season)```show the stats of everyone in a role, the total average and the 6 best average, stat let you choose the type of stats (default is mmr), season let you choose the season to check the stats from (default to current season)",
            inline=False,
        )
        embeds[-1].add_field(
            name="mkc stats",
            value="```/mkc_stats team (stat) (season)```show the stats of everyone in a mkc 150cc team roster, the total average and the 6 best average, stat let you choose the type of stats (default is mmr), season let you choose the season to check the stats from (default to current season)",
            inline=False,
        )
        embeds[-1].add_field(
            name="fc stats",
            value="```/fc_stats room (team_size) (stat) (season)```show the stats of a room using friend codes, it needs to be a room of 12 and while team_size is optional you should set it to have proper stats for each teams, room is where you paste your room info",
            inline=False,
        )
        embeds[-1].add_field(
            name="name history",
            value="```/name_history (player)```show the tracked name history with date of the selected player (you if player is not provided), and show when you will be able to change your name again",
            inline=False,
        )
        embeds[-1].add_field(
            name="lounge profile",
            value="```/lounge_profile (player)```show the lounge profile of the selected player (you if player is not provided) with MMR graph and detailed statistics",
            inline=False,
        )

        embeds.append(
            discord.Embed(
                color=0x47E0FF,
                title="War stats commands",
                description="this section is about stats on played tracks in war, using <@177162177432649728> (Toad) Quaxly will automatically track stats on each track for you (each channel or thread counts as a different team and only people that have access to it can see its stats)",
            )
        )

        embeds[-1].add_field(
            name="war list",
            value="```/war list (channel)```show the list of recorded wars with their IDs for the selected channel or thread (if none is provided it will use the current one)",
            inline=False,
        )
        embeds[-1].add_field(
            name="war delete",
            value="```/war delete (channel) (war_id)```let you delete a war (or all of them if you do not provide a war id), for the selected channel or thread (or the current one if none is provided)",
            inline=False,
        )
        embeds[-1].add_field(
            name="war stats",
            value="```/war stats (channel) (minimum) (track) (team)```show the stats for each track from best to worst in the selected channel or thread (if none is provided it will use the current one), minimum is the minimum times a track needs to be played to count in the stats (default to 1), track is an option to view stats from one track only, team lets you filter by a specific team tag",
            inline=False,
        )
        embeds[-1].add_field(
            name="war copy",
            value="```/war copy source destination```copy all war stats from one channel or thread to another (source data is kept untouched), useful to migrate stats when reorganizing channels into threads, requires manage messages permission in both source and destination",
            inline=False,
        )

        embeds.append(
            discord.Embed(
                color=0x47E0FF,
                title="War bot commands",
                description="this is a war bot implementation like sokuji with overlay support",
            )
        )

        embeds[-1].add_field(
            name="war start",
            value="```/war start tag enemy_tag (game)```start a war with selected teams (MK8DX and Mario Kart World are 6v6, Mario Kart Wii is 5v5), provides an overlay link for streaming",
            inline=False,
        )
        embeds[-1].add_field(
            name="war system",
            value="**1:** you are supposed to type the map abbreviation in the war channel when it gets picked\n\n**2:** type score all attached to each other in order (example: `134568`) to count a race\n**warning** bottom spots are added automatically so you never have to type 12 for example\n`-` is a range and if at the start can be used to specify the top spots (example: `-379` would be top3 7 9 and 12)\n\n**3:** mistyped something? Just type `back` and it will erase the last race\n\n**4:** want to add a track afterward? You can type `race <nb> <track>` to change it (example: `race 7 bdd`)\n\n**5:** use `/war edit_race` to modify positions for a specific race\n\n**6:** use `/war track` to set the upcoming track before the race starts\n\n**7:** type `pen <points>` to give a penalty to the enemy team (example: `pen 10`), use a negative value to penalize your own team (example: `pen -10`), mistyped? `unpen <points>` reverts it the same way (example: `unpen 10` removes a 10 points penalty from the enemy team)",
            inline=False,
        )
        embeds[-1].add_field(
            name="war stop",
            value="```/war stop```stop the current war, you don't really have to type this if you don't usually type in the channel, wars reset automatically if you start a new one and timeout after some time",
            inline=False,
        )

        embeds.append(discord.Embed(color=0x47E0FF, title="Utility"))

        embeds[-1].add_field(
            name="tracks",
            value="```/tracks (game)```show a message with all the cups in the selected game as buttons (MK8DX or Mario Kart World), pressing a button will show you the track name to use for the 4 tracks of the selected cup. For Mario Kart World it shows a simple list of all tracks.",
        )
        embeds[-1].add_field(
            name="debug",
            value="```/debug```show the bot debug info including API response times",
        )
        embeds[-1].add_field(
            name="lineup (DEPRECATED)",
            value="```/lineup players time host enemy_tag tag```⚠️ **This command is deprecated and will be removed in a future update.** It is no longer maintained and may not work properly. Please use alternative methods for creating lineups.",
            inline=False,
        )
        embeds[-1].add_field(
            name="get in contact with me",
            value="if you want a new command, some improvement, a bug, or even just some questions I'll be happy to help you!\nhere's how to contact me:\n- discord: prrh (<@169497208406802432>)\n- support server: https://discord.gg/xucEGtxU9n\n- twitter: [@prismcmoi](https://twitter.com/prismcmoi)",
            inline=False,
        )

        await interaction.response.send_message(
            embed=embeds[0],
            view=Paginator(interaction=interaction, embeds=embeds),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
