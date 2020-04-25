import asyncio
import datetime
import os
import gc
import discord

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
ADMIN_ROLE = os.getenv('ADMIN_ROLE')

bot = commands.Bot(command_prefix='!')
client = discord.Client()

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
        self.message_start = 'Conflicts report:\n\n'
        self.comment = ''
        self.report = ''
        self.report_message_id = 0

    def updated_ago_text(self, updated_ago):
        if (
                updated_ago[-2:] == '1' or
                updated_ago[-2:] == '21'
        ):
            text = f'{updated_ago} hour ago.'
        elif updated_ago[-2:] == '0':
            text = 'less than an hour ago.'
        else:
            text = f'{updated_ago} hours ago.'
        return text

    def report_active(self, cache):
        if self.cache_old is None:
            pass
        else:
            if cache() == self.cache_old():
                return

        if len(cache.conflicts_active) == 0:
            self.report += f'Our kingdom is at peace! (for now)\n\n'
        else:
            for conflict in cache.conflicts_active:
                if conflict not in self.conflicts_active_order:
                    self.conflicts_active_order[conflict] = {
                        'score_us': cache.conflicts_active[conflict]['score_us'],
                        'score_them': cache.conflicts_active[conflict]['score_them'],
                        'updated_ago': cache.conflicts_active[conflict]['updated_ago'],
                        'new': True
                    }

            self.report += f'Active conflicts:\n\n'
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

                    self.report += '{0}: {1} in {2}\n' \
                                   '{3} [ {4} - {5} ] {6}\n'.format(
                                    idx+1,
                                    cache.conflicts_active[conflict]["state"].capitalize(),
                                    system,
                                    FACTION_NAME,
                                    score_us,
                                    score_them,
                                    cache.conflicts_active[conflict]["opponent"],
                                    )

                    if cache.conflicts_active[conflict]['win']:
                        self.report += f'On victory we gain: {cache.conflicts_active[conflict]["win"]}\n'

                    if cache.conflicts_active[conflict]['loss']:
                        self.report += f'On defeat we lose: {cache.conflicts_active[conflict]["loss"]}\n'

                    self.report += f'Last updated: ' \
                                   f'{self.updated_ago_text(cache.conflicts_active[conflict]["updated_ago"])}\n\n'

    def report_recovering(self, cache):
        if len(cache.conflicts_recovering) == 0:
            pass
        else:
            self.report += 'Recovering from conflicts:\n\n'
            for idx, conflict in enumerate(cache.conflicts_recovering):
                state = cache.conflicts_recovering[conflict]["state"]
                status = cache.conflicts_recovering[conflict]["status"]
                stake = cache.conflicts_recovering[conflict]["stake"]
                self.report += '{0}: {1} in {2} - {3}. '.format(
                                idx+1,
                                state.capitalize(),
                                conflict,
                                status.capitalize(),
                                )
                if stake:
                    if status == 'victory':
                        self.report += f'We won {stake}\n'
                    if status == 'defeat':
                        self.report += f'We lost {stake}\n'
                else:
                    self.report += '\n'
                self.report += f'Last updated: ' \
                               f'{self.updated_ago_text(cache.conflicts_recovering[conflict]["updated_ago"])}\n\n'

    def report_pending(self, cache):
        if len(cache.conflicts_pending) == 0:
            pass
        else:
            self.report += 'Pending conflicts:\n\n'
            for idx, conflict in enumerate(cache.conflicts_pending):
                state = cache.conflicts_pending[conflict]["state"]
                self.report += '{0}: {1} in {2}.\n'.format(
                                idx+1,
                                state.capitalize(),
                                conflict,
                                )
                if cache.conflicts_pending[conflict]['win']:
                    self.report += f'On victory we gain: {cache.conflicts_pending[conflict]["win"]}\n'

                if cache.conflicts_pending[conflict]['loss']:
                    self.report += f'On defeat we lose: {cache.conflicts_pending[conflict]["loss"]}\n'

                self.report += f'Last updated: ' \
                               f'{self.updated_ago_text(cache.conflicts_pending[conflict]["updated_ago"])}\n\n'

    @tasks.loop(minutes=60)
    async def send_report(self):
        self.cache = Cache()
        cache = self.cache

        self.report_active(cache)
        self.report_recovering(cache)
        self.report_pending(cache)

        if DEBUG:
            await purge(CHANNEL_ADMIN)

        if self.comment == '':
            await bot.get_channel(CHANNEL_ADMIN).send(f'{self.message_start}{self.report}')
        else:
            await bot.get_channel(CHANNEL_ADMIN).send(f'{self.message_start}{self.comment}\n\n{self.report}')

        self.cache_old = cache

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            global report_message_id
            report_message_id = message.id
        await bot.process_commands(message)


@bot.command(name='comment')
@commands.has_role(ADMIN_ROLE)
async def comment(ctx, arg):
    for obj in gc.get_objects():
        if isinstance(obj, HourlyReport):

            msg = await ctx.channel.fetch_message(report_message_id)
            await msg.delete()

            obj.comment = arg
            if obj.comment == '':
                await bot.get_channel(CHANNEL_ADMIN).send(f'{obj.message_start}{obj.report}')
            else:
                await bot.get_channel(CHANNEL_ADMIN).send(f'{obj.message_start}{obj.comment}\n\n{obj.report}')

    await ctx.message.delete()


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
