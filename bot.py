import asyncio
import os
import string
from collections import OrderedDict
from datetime import datetime
from datetime import timedelta

import pytz
import discord
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

from eddb_api import Cache

# TODO: check for number of symbols in report (max 2000)
# TODO: add command for checking the best LTD selling station
# TODO: aiohttp for requests
# TODO: add logging
# TODO: add reaction mechanics
# TODO: add links to systems and stations on EDDB or Inara

load_dotenv()  # All environment variables are stored in '.env' file
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')
CHANNEL_ADMIN = int(os.getenv('CHANNEL_ADMIN'))
ADMIN_ROLE = os.getenv('ADMIN_ROLE')

bot = commands.Bot(command_prefix='!')
client = discord.Client()

number_emoji = (':zero:', ':one:', ':two:', ':three:', ':four:', ':five:',
                ':six:', ':seven:', ':eight:', ':nine:', ':keycap_ten:')
errors_text = {1: '`Error` No such faction. Please check faction name and try again.'}
frontier_tz = pytz.timezone('UTC')
frontier_time = datetime.now(frontier_tz)


'''What I do on startup'''


@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}')
    print('\n')
    await bot_start()


'''What I can do on my own'''


async def bot_start():
    global hr
    hr = HourlyReport(bot)
    hr.report_loop.start()


async def purge_own_messages(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=100).flatten():
        if message.author == bot.user:
            await message.delete()


async def purge_commands(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=100).flatten():
        if message.content.startswith('!'):
            await message.delete()


@bot.event
async def on_message(message):
    if (
            message.author == bot.user and
            hr.message_start in message.content
    ):
        global report_message_id
        report_message_id = message.id
    await bot.process_commands(message)


class HourlyReport:
    def __init__(self, bot):
        self.bot = bot
        self.conflicts_active_order = OrderedDict()
        self.message_start = f'Current objectives for {os.getenv("FACTION_NAME")}:\n\n'
        self.comment = ''
        self.event = {}
        self.report_message_id = 0

    def updated_ago_text(self, updated_at):
        updated_at = frontier_tz.localize(datetime.strptime(updated_at[0:16], '%Y-%m-%dT%H:%M'))
        updated_ago = str(frontier_time - updated_at)[:-13]
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

    def report_active(self, conflicts_active, start_num):
        text = ''
        if len(conflicts_active) == 0:
            text = 'No ongoing conflicts :sleeping:\n\n'
        else:
            for conflict in conflicts_active:
                if conflict not in self.conflicts_active_order:
                    self.conflicts_active_order[conflict] = {
                        'score_us': conflicts_active[conflict]['score_us'],
                        'score_them': conflicts_active[conflict]['score_them'],
                        'new': True
                    }
            for idx, conflict in enumerate(self.conflicts_active_order):
                if conflict not in conflicts_active:
                    self.conflicts_active_order.pop(conflict)
                else:
                    score_us = conflicts_active[conflict]["score_us"]
                    if conflicts_active[conflict]['score_us'] != self.conflicts_active_order[conflict]['score_us']:
                        score_us = f'**{conflicts_active[conflict]["score_us"]}**'

                    score_them = conflicts_active[conflict]["score_them"]
                    if conflicts_active[conflict]['score_them'] != self.conflicts_active_order[conflict]['score_them']:
                        score_them = f'**{conflicts_active[conflict]["score_them"]}**'

                    system = conflict
                    if self.conflicts_active_order[conflict]['new']:
                        system = f'**{conflict}**:exclamation:'

                    num = number_emoji[idx + start_num]
                    text += '{0} - {1} in {2}\n' \
                            '{3} [ {4} - {5} ] {6}\n'.format(
                             num,
                             conflicts_active[conflict]["state"].capitalize(),
                             system,
                             os.getenv("FACTION_NAME"),
                             score_us,
                             score_them,
                             conflicts_active[conflict]["opponent"],
                             )
                    if conflicts_active[conflict]['win']:
                        text += f'On victory we gain: *{conflicts_active[conflict]["win"]}*\n'
                    if conflicts_active[conflict]['loss']:
                        text += f'On defeat we lose: *{conflicts_active[conflict]["loss"]}*\n'
                    if not conflicts_active[conflict]['win'] and not conflicts_active[conflict]['loss']:
                        text += '*No stakes*\n'

                    updated_at = conflicts_active[conflict]["updated_at"]
                    updated_at_time = frontier_tz.localize(datetime.strptime(updated_at[0:16], '%Y-%m-%dT%H:%M'))
                    if (frontier_time - updated_at_time) >= timedelta(hours=12):
                        text += f'Last updated: **{self.updated_ago_text(updated_at)}**\n\n'
                    else:
                        text += f'Last updated: {self.updated_ago_text(updated_at)}\n\n'
        self.report += text

    def report_pending(self, conflicts_pending):
        text = ''
        if len(conflicts_pending) == 0:
            pass
        else:
            for conflict in conflicts_pending:
                state = conflicts_pending[conflict]["state"]
                text += f':arrow_up: - *Pending* {state.capitalize()} in {conflict}\n'

                if conflicts_pending[conflict]['win']:
                    text += f'On victory we gain: *{conflicts_pending[conflict]["win"]}*\n'
                if conflicts_pending[conflict]['loss']:
                    text += f'On defeat we lose: *{conflicts_pending[conflict]["loss"]}*\n'
                if not conflicts_pending[conflict]['win'] and not conflicts_pending[conflict]['loss']:
                    text += '*No stakes*\n'

                updated_at = conflicts_pending[conflict]["updated_at"]
                updated_at_time = frontier_tz.localize(datetime.strptime(updated_at[0:16], '%Y-%m-%dT%H:%M'))
                if (frontier_time - updated_at_time) >= timedelta(hours=12):
                    text += f'Last updated: **{self.updated_ago_text(updated_at)}**\n\n'
                else:
                    text += f'Last updated: {self.updated_ago_text(updated_at)}\n\n'
        self.report += text

    def report_recovering(self, conflicts_recovering):
        text = ''
        if len(conflicts_recovering) == 0:
            pass
        else:
            for conflict in conflicts_recovering:
                state = conflicts_recovering[conflict]["state"]
                status = conflicts_recovering[conflict]["status"]
                stake = conflicts_recovering[conflict]["stake"]
                text += f':arrow_down: - *Recovering* from {state.capitalize()} in {conflict} - {status.capitalize()}'
                if stake:
                    if status == 'victory':
                        text += f', we won *{stake}*\n\n'
                    if status == 'defeat':
                        text += f', we lost *{stake}*\n\n'
                else:
                    text += '!\n\n'
        self.report += text

    def unvisited_systems_text(self, unvisited_systems):
        text = 'Systems unchecked for:\n'
        lines = 1
        for day in unvisited_systems:
            if unvisited_systems[day]:
                lines += 1
                if 5 <= day <= 6:
                    text += f'**{day} days**: '
                elif day == 7:
                    text += f':exclamation:**Over a week**: '
                else:
                    text += f'{day} days: '
                text += ', '.join(unvisited_systems[day])
                text += '\n'
        if lines == 1:
            return
        elif lines == 2:
            text = text.replace(':\n', ' ')
        self.report += text

    async def report_send(self):
        self.report = ''
        start_num = len(self.event) + 1
        self.report_active(self.cache.conflicts_active, start_num)
        self.report_pending(self.cache.conflicts_pending)
        self.report_recovering(self.cache.conflicts_recovering)
        self.unvisited_systems_text(self.cache.unvisited_systems)

        await purge_own_messages(CHANNEL_ADMIN)

        report = self.message_start
        if self.comment:
            report += f'{self.comment}\n\n'
        if self.event:
            for ev in self.event:
                report += f'{number_emoji[ev]} - {self.event[ev]}\n\n'
        report += self.report
        await bot.get_channel(CHANNEL_ADMIN).send(report)

    @tasks.loop(minutes=30)
    async def report_loop(self):
        await bot.get_channel(CHANNEL_ADMIN).send(f'`Updating report...`')
        self.cache = Cache()
        if self.cache.faction_data['error'] != 0:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[self.cache.faction_data['error']])
            return
        await self.report_send()

        await purge_commands(CHANNEL_ADMIN)


'''Commands I understand'''


@bot.command(name='comment',
             brief='Adds comment to the report',
             description='Adds text at the top of the report. To remove comment, pass plain command. '
                         'To add multiple lines, wrap text into "".')
@commands.has_role(ADMIN_ROLE)
async def comment(ctx, *args):
    hr.comment = (' '.join(args))

    await hr.report_send()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='event',
             brief='Adds event to the report',  # TODO: update command description
             description='Adds text after comment and before active conflicts to the report. '
                         'Marks it as the first objective. To remove objective, pass plain command. '
                         'To add multiple lines, wrap text into "".')
@commands.has_role(ADMIN_ROLE)
async def event(ctx, arg_num=None, *args):
    if not arg_num:
        hr.event = {}
    elif not arg_num.isnumeric():
        hr.event[1] = f'{arg_num} '
        hr.event[1] += (' '.join(args))
    else:
        for num in range(1, int(arg_num)):
            if num not in hr.event:
                hr.event[num] = ''
        hr.event[int(arg_num)] = (' '.join(args))

        for num in range(len(hr.event), 0):
            print(num, int(arg_num))
            if not hr.event[int(arg_num)]:
                hr.event.pop(num)

    await hr.report_send()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='order',
             brief='Reorders active conflicts',
             description='Reorders active conflicts. Use a set of numbers with no spaces.')
@commands.has_role(ADMIN_ROLE)
async def order(ctx, arg):
    new_order = OrderedDict()
    if len(arg) != len(hr.conflicts_active_order):
        await bot.get_channel(CHANNEL_ADMIN).send(f'There are {len(hr.conflicts_active_order)} active conflicts. '
                                                  f'Please try again.')
        return

    for num in range(1, len(hr.conflicts_active_order) + 1):
        if str(num) not in arg:
            await bot.get_channel(CHANNEL_ADMIN).send(f'Typo?')
            return

    for num in arg:
        for idx, conflict in enumerate(hr.conflicts_active_order):
            if idx + 1 == int(num):
                new_order[conflict] = hr.conflicts_active_order[conflict]
    hr.conflicts_active_order = new_order

    await hr.report_send()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='seen',
             brief='Marks report as seen and removes highlights',
             description='Marks report as seen and removes highlights')
@commands.has_role(ADMIN_ROLE)
async def seen(ctx):
    for conflict in hr.conflicts_active_order:
        hr.conflicts_active_order[conflict]['score_us'] = hr.cache.conflicts_active[conflict]['score_us']
        hr.conflicts_active_order[conflict]['score_them'] = hr.cache.conflicts_active[conflict]['score_them']
        hr.conflicts_active_order[conflict]['new'] = False

    await hr.report_send()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='faction',
             brief='Changes the followed faction',
             description='Changes the followed faction')
@commands.has_role(ADMIN_ROLE)
async def faction(ctx, *args):
    await bot.get_channel(CHANNEL_ADMIN).send(f'`Changing faction...`')
    os.environ['FACTION_NAME'] = string.capwords(' '.join(args))
    hr.report_loop.cancel()     # object NoneType can't be used in 'await' expression
    await asyncio.sleep(3)      # TODO: fix this with a proper await
    await bot_start()


bot.run(TOKEN)
