import asyncio
import os
from collections import OrderedDict

import discord
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

from eddb_api import Cache

# TODO: aiohttp for requests
# TODO: add logging
# TODO: change event to allow for multiple extra objectives
# TODO: check for number of symbols in report (max 2000)
# TODO: add links to systems and stations on EDDB or Inara

load_dotenv()   # All environment variables are stored in '.env' file
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')
CHANNEL_ADMIN = int(os.getenv('CHANNEL_ADMIN'))
ADMIN_ROLE = os.getenv('ADMIN_ROLE')

bot = commands.Bot(command_prefix='!')
client = discord.Client()

number_emoji = (':zero:', ':one:', ':two:', ':three:', ':four:', ':five:',
                ':six:', ':seven:', ':eight:', ':nine:', ':ten:')


'''What I do on startup'''


@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}\n')
    await bot_start()


'''What I can do on my own'''


async def bot_start():
    global hr
    hr = HourlyReport(bot)
    hr.report_loop.start()


async def purge_own_messages(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=200).flatten():
        if message.author == bot.user:
            await message.delete()


async def purge_commands(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=200).flatten():
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
        self.event = ''
        self.report_message_id = 0

    def report_active(self, conflicts_active, number):
        if len(conflicts_active) == 0:
            text = f'Our Empire is at peace (for now).\n\n'
        else:
            for conflict in conflicts_active:
                if conflict not in self.conflicts_active_order:
                    self.conflicts_active_order[conflict] = {
                        'score_us': conflicts_active[conflict]['score_us'],
                        'score_them': conflicts_active[conflict]['score_them'],
                        'updated_ago': conflicts_active[conflict]['updated_ago'],
                        'new': True
                    }
            text = f'Active conflicts:\n\n'
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

                    num = number_emoji[idx+number]
                    text += '{0} - {1} in {2}\n' \
                            '{3} [ {4} - {5} ] {6}\n'.format(
                             num,
                             conflicts_active[conflict]["state"].capitalize(),
                             system,
                             os.getenv('FACTION_NAME'),
                             score_us,
                             score_them,
                             conflicts_active[conflict]["opponent"],
                             )
                    if conflicts_active[conflict]['win']:
                        text += f'On victory we gain: *{conflicts_active[conflict]["win"]}*\n'
                    if conflicts_active[conflict]['loss']:
                        text += f'On defeat we lose: *{conflicts_active[conflict]["loss"]}*\n'

                    if len(conflicts_active[conflict]["updated_ago"]) > 12:
                        text += f'Last updated: **{conflicts_active[conflict]["updated_ago"]}**\n\n'
                    else:
                        text += f'Last updated: {conflicts_active[conflict]["updated_ago"]}\n\n'
            self.report += text

    def report_pending(self, conflicts_pending):
        text = ''
        if len(conflicts_pending) == 0:
            pass
        else:
            for conflict in conflicts_pending:
                state = conflicts_pending[conflict]["state"]
                text += f':arrow_up: - *Pending* {state.capitalize()} in {conflict}.\n'

                if conflicts_pending[conflict]['win']:
                    text += f'On victory we gain: *{conflicts_pending[conflict]["win"]}*\n'
                if conflicts_pending[conflict]['loss']:
                    text += f'On defeat we lose: *{conflicts_pending[conflict]["loss"]}*\n'

                if len(conflicts_pending[conflict]["updated_ago"]) > 12:
                    text += f'Last updated: **{conflicts_pending[conflict]["updated_ago"]}**\n\n'
                else:
                    text += f'Last updated: {conflicts_pending[conflict]["updated_ago"]}\n\n'
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
                text += f':arrow_down: - *Recovering from* {state.capitalize()} in {conflict} - {status.capitalize()}. '
                if stake:
                    if status == 'victory':
                        text += f'We won {stake}\n\n'
                    if status == 'defeat':
                        text += f'We lost {stake}\n\n'
                else:
                    text += '\n\n'
        self.report += text

    def unvisited_systems(self, unvisited_systems):
        text = 'Systems unchecked for:\n'
        for day in unvisited_systems:
            if day == 7:
                text += f':exclamation:**A week or more**: {unvisited_systems[day]}'
            elif unvisited_systems[day]:
                text += f'{day} days: {unvisited_systems[day]}\n'

        if text.endswith('Systems unchecked for:'):
            text.replace('Systems unchecked for:', '')

        to_replace = ('[', ']', "'")
        for symbol in to_replace:
            text = text.replace(symbol, '')
        self.report += text

    async def report_send(self):
        self.report = ''
        number = 1
        if self.event:
            number = 2
        self.report_active(self.cache.conflicts_active, number)
        self.report_pending(self.cache.conflicts_pending)
        self.report_recovering(self.cache.conflicts_recovering)
        self.unvisited_systems(self.cache.unvisited_systems)

        await purge_own_messages(CHANNEL_ADMIN)

        report = self.message_start
        if self.comment:
            report += f'{self.comment}\n\n'
        if self.event:
            report += f':one: - {self.event}\n\n'
        report += self.report
        await bot.get_channel(CHANNEL_ADMIN).send(report)

    @tasks.loop(minutes=30)
    async def report_loop(self):
        self.cache = Cache()
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
             brief='Adds event to the report',
             description='Adds text after comment and before active conflicts to the report. '
                         'Marks it as the first objective. To remove objective, pass plain command. '
                         'To add multiple lines, wrap text into "".')
@commands.has_role(ADMIN_ROLE)
async def comment(ctx, *args):
    hr.event = (' '.join(args))

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

    for num in range(1, len(hr.conflicts_active_order)+1):
        if str(num) not in arg:
            await bot.get_channel(CHANNEL_ADMIN).send(f'Typo?')
            return

    for num in arg:
        for idx, conflict in enumerate(hr.conflicts_active_order):
            if idx+1 == int(num):
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
        hr.conflicts_active_order[conflict]['updated_ago'] = hr.cache.conflicts_active[conflict]['updated_ago']
        hr.conflicts_active_order[conflict]['new'] = False

    await hr.report_send()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='faction',
             brief='Changes the followed faction',
             description='Changes the followed faction')
@commands.has_role(ADMIN_ROLE)
async def faction(ctx, *args):
    await bot.get_channel(CHANNEL_ADMIN).send(f'Working...')
    os.environ['FACTION_NAME'] = (' '.join(args))
    hr.report_loop.cancel()     # object NoneType can't be used in 'await' expression
    await asyncio.sleep(3)      # TODO: fix this with a proper await
    await bot_start()

    await purge_commands(CHANNEL_ADMIN)


bot.run(TOKEN)
