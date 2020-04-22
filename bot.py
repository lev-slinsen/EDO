import asyncio
import datetime
import os

from collections import OrderedDict
from discord.ext import commands
from discord.ext import tasks
from discord.ext.commands import CommandNotFound
from dotenv import load_dotenv

from eddb_api import Cache

load_dotenv()   # All environment variables are stored in '.env' file
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')
FACTION_NAME = os.getenv('FACTION_NAME')
CHANNEL_ADMIN = int(os.getenv('CHANNEL_ADMIN'))
CHANNEL_USER = int(os.getenv('CHANNEL_USER'))
ADMIN_ROLE = os.getenv('ADMIN_ROLE')

bot = commands.Bot(command_prefix='!')

'''What I do on startup'''


@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}\n')

    HourlyReport(bot).send_report.start()


'''What I can do on my own'''


async def purge(channel_to):
    channel = bot.get_channel(channel_to)
    await channel.purge()


class HourlyReport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conflicts_active_order = OrderedDict()
        self.cache_old = None

    @tasks.loop(minutes=60)
    async def send_report(self):
        self.cache = Cache()
        cache = self.cache

        if self.cache_old is None:
            pass
        else:
            if cache() == self.cache_old():
                await bot.get_channel(CHANNEL_ADMIN).send(f"Ok, people, move along! There's nothing to see here.")
                return

        report = f"@{ADMIN_ROLE} Today's special menu:\n"

        await purge(CHANNEL_ADMIN)

        if len(cache.conflicts_active) == 0:
            report += f'Our kingdom is at peace! (for now)\n\n'
        else:

            for conflict in cache.conflicts_active:
                if conflict not in self.conflicts_active_order:
                    self.conflicts_active_order[conflict] = {
                        'score_us': cache.conflicts_active[conflict]['score_us'],
                        'score_them': cache.conflicts_active[conflict]['score_them'],
                        'updated_ago': cache.conflicts_active[conflict]['updated_ago'],
                        'new': True
                    }

            report += f'Active conflicts:\n\n'
            for idx, conflict in enumerate(self.conflicts_active_order):
                if conflict not in cache.conflicts_active:
                    self.conflicts_active_order.pop(conflict)
                else:
                    if cache.conflicts_active[conflict]['score_us'] != \
                            self.conflicts_active_order[conflict]['score_us']:
                        score_us = f'**{cache.conflicts_active[conflict]["score_us"]}**'
                    else:
                        score_us = cache.conflicts_active[conflict]["score_us"]

                    if cache.conflicts_active[conflict]['score_them'] != \
                            self.conflicts_active_order[conflict]['score_them']:
                        score_them = f'**{cache.conflicts_active[conflict]["score_them"]}**'
                    else:
                        score_them = cache.conflicts_active[conflict]["score_them"]

                    if self.conflicts_active_order[conflict]['new']:
                        system = f'**{conflict}**:exclamation:'
                    else:
                        system = conflict

                    if (
                            cache.conflicts_active[conflict]["updated_ago"][-2:] == '1' or
                            cache.conflicts_active[conflict]["updated_ago"][-2:] == '21'
                    ):
                        h_text = f'{cache.conflicts_active[conflict]["updated_ago"]} hour ago.'
                    elif cache.conflicts_active[conflict]["updated_ago"][-2:] == '0':
                        h_text = 'less than an hour ago.'
                    else:
                        h_text = f'{cache.conflicts_active[conflict]["updated_ago"]} hours ago.'

                    report += '{0}: {1} in {2}\n' \
                              '{3} [ {4} - {5} ] {6}\n' \
                              'Last updated: {7}\n\n'.format(
                                idx,
                                cache.conflicts_active[conflict]["state"].capitalize(),
                                system,
                                FACTION_NAME,
                                score_us,
                                score_them,
                                cache.conflicts_active[conflict]["opponent"],
                                h_text
                              )
        await bot.get_channel(CHANNEL_ADMIN).send(report)
        self.cache_old = cache


'''How I handle errors'''


@bot.event
async def on_command_error(ctx, error):     # Hides 'command not found' errors in console
    if isinstance(error, CommandNotFound):
        return
    raise error


@bot.event
async def on_command_error(ctx, error):     # Logs errors into 'err.log' file
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have required role for this command.')
        with open('EDO/err.log', 'a+') as err_log:
            print(f'{datetime.datetime.now()}, User: {ctx.author}\n'
                  f'Command: {ctx.command}, Error: Role check failure\n')
            err_log.write(f'{datetime.datetime.now()}, User: {ctx.author}\n'
                          f'Command: {ctx.command}, Error: Role check failure\n')


bot.run(TOKEN)
