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
errors_text = {1: '`Error` No such faction. Please check faction name and try again.',
               2: '`Error` Unable to add comment to this objective. '
                  'Instead, try changing objective text with the `!event` command',
               3: 'There is no event to delete.',
               4: 'There are multiple events, please select the one to delete with respective number.',
               5: 'Incorrect event selected for change.',
               6: "There's a different number of objectives, please try again.",
               7: 'Typo?'}
frontier_tz = pytz.timezone('UTC')
frontier_time = datetime.now(frontier_tz)


'''What I do on startup'''


@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}')
    print()
    await bot_start()


async def bot_start():
    global auto_report
    auto_report = AutoReport(bot)
    auto_report.report_loop.start()


class Objective:
    def __init__(self):
        self.status = ''
        self.state = ''
        self.opponent = ''
        self.score_us = ''
        self.score_them = ''
        self.win = ''
        self.loss = ''
        self.updated_ago = ''
        self.comment = ''
        self.text = ''

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

    async def conflict_active_text(self, num, system_name):
        text = '{0} {1} in **{2}**\n' \
               '{3} [ {4} - {5} ] {6}\n'.format(
                number_emoji[num],
                self.state.capitalize(),
                system_name,
                os.getenv("FACTION_NAME"),
                self.score_us,
                self.score_them,
                self.opponent
                )
        if self.win:
            text += f'On victory we gain: *{self.win}*\n'
        if self.loss:
            text += f'On defeat we lose: *{self.loss}*\n'
        text += f'Updated {self.updated_ago_text(self.updated_ago)}\n'
        if self.comment:
            text += f'\n{self.comment}\n\n'
        else:
            text += '\n'
        return text


class AutoReport:
    def __init__(self, bot):
        self.bot = bot
        self.objectives = OrderedDict()
        self.comment = ''
        self.report_message_id = 0

    @tasks.loop(minutes=30)
    async def report_loop(self):
        await bot.get_channel(CHANNEL_ADMIN).send(f'`Updating report...`')
        self.cache = Cache()
        if self.cache.faction_data['error'] != 0:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[self.cache.faction_data['error']])
            return
        await self.objectives_collect()
        await purge_own_messages(CHANNEL_ADMIN)
        await self.report_send()
        await purge_commands(CHANNEL_ADMIN)

    async def objectives_collect(self):
        self.report_active(self.cache.conflicts_active)
        # self.report_pending(self.cache.conflicts_pending)
        # self.report_recovering(self.cache.conflicts_recovering)
        # self.unvisited_systems_text(self.cache.unvisited_systems)

    async def report_send(self):
        report = f'Current objectives for {os.getenv("FACTION_NAME")}:\n\n'
        if self.comment:
            report += f'{self.comment}\n\n'
        for num, objective_name in enumerate(self.objectives):
            objective = self.objectives[objective_name]
            if objective.status == 'active':
                report += await objective.conflict_active_text(num + 1, objective_name)
            elif objective.status == 'event':
                report += f'{number_emoji[num + 1]} {objective.text}\n\n'
        await bot.get_channel(CHANNEL_ADMIN).send(report)

    def report_active(self, conflicts_active):
        for conflict in conflicts_active:
            for old_objective in self.objectives:
                if old_objective not in conflicts_active:
                    self.objectives.pop(conflict)
            if conflict not in self.objectives:
                self.objectives[conflict] = Objective()
                objective = self.objectives[conflict]
                objective.status = 'active'
                objective.state = conflicts_active[conflict]['state']
                objective.opponent = conflicts_active[conflict]['opponent']
                objective.score_us = conflicts_active[conflict]['score_us']
                objective.score_them = conflicts_active[conflict]['score_them']
                objective.win = conflicts_active[conflict]['win']
                objective.loss = conflicts_active[conflict]['loss']
                objective.updated_ago = conflicts_active[conflict]['updated_at']
            else:
                objective = self.objectives[conflict]
                objective.score_us = conflicts_active[conflict]['score_us']
                objective.score_them = conflicts_active[conflict]['score_them']
                objective.updated_ago = conflicts_active[conflict]['updated_at']


# @bot.event
# async def on_message(message):
#     if (
#             message.author == bot.user and
#             auto_report.message_start in message.content
#     ):
#         global report_message_id
#         report_message_id = message.id
#     await bot.process_commands(message)


async def purge_own_messages(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=100).flatten():
        if message.author == bot.user:
            await message.delete()


async def purge_commands(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=100).flatten():
        if message.content.startswith('!'):
            await message.delete()


'''Commands I understand'''


@bot.command(name='comment',
             brief='Adds comments to the report or objectives',
             description='Adds text at the top of the report.\n'
                         'To add comment to the specific objective, pass objective number as the first word.\n'
                         'To remove general comment, pass plain command or '
                         'objective number with no other text to remove comment for that objective.\n'
                         'To add multiple lines, wrap text into "".')
@commands.has_role(ADMIN_ROLE)
async def comment(ctx, arg_num=None, *args):
    if not arg_num:
        auto_report.comment = ''
    elif arg_num.isnumeric():
        arg_num = int(arg_num)
        if 1 <= arg_num <= len(auto_report.objectives):
            arg_num -= 1
            for num, objective in enumerate(auto_report.objectives):
                if int(arg_num) == num:
                    auto_report.objectives[objective].comment = (' '.join(args))
        else:
            for num, objective in enumerate(auto_report.objectives):
                if int(arg_num) == num:
                    if auto_report.objectives[objective].status != 'active':
                        await bot.get_channel(CHANNEL_ADMIN).send(errors_text[2])
    else:
        auto_report.comment = f'{arg_num} ' + (' '.join(args))

    await purge_own_messages(CHANNEL_ADMIN)
    await auto_report.report_send()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='event',
             brief='Adds event to the report',
             description='Adds a custom event to the objectives list.\n'
                         "To change a specific event, pass it's number on the list first\n"
                         "To remove an event, pass empty command. "
                         "If there are multiple events, pass only it's number with no further words\n"
                         'To add multiple lines, wrap text into "".')
@commands.has_role(ADMIN_ROLE)
async def event(ctx, arg_num=None, *args):
    objectives = auto_report.objectives
    if not arg_num:
        count = 0
        for objective in objectives:
            if objective.startswith('event'):
                count += 1
        if count <= 0:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[3])
            return
        elif count >= 2:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[4])
            return
        else:
            for objective in objectives:
                if objective.startswith('event'):
                    objectives.pop(objective)
    elif arg_num.isnumeric():
        changed = 0
        for num, objective in enumerate(objectives):
            if objective == f'event {arg_num}':
                objectives[f'event {arg_num}'].text = (' '.join(args))
                changed += 1
        if changed == 0:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[5])
            return
        if not args:
            objectives.pop(f'event {arg_num}')
    else:
        objectives[f'event {len(objectives) + 1}'] = Objective()
        objective = objectives[f'event {len(objectives)}']
        objective.status = 'event'
        objective.text = f'{arg_num} ' + (' '.join(args))

    await purge_own_messages(CHANNEL_ADMIN)
    await auto_report.report_send()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='order',
             brief='Puts objectives in a different order',
             description='Puts objectives in a different order. Pass a set of numbers with no spaces.')
@commands.has_role(ADMIN_ROLE)
async def order(ctx, arg):
    new_order = OrderedDict()
    if len(arg) != len(auto_report.objectives):
        await bot.get_channel(CHANNEL_ADMIN).send(errors_text[6])
        return
    for num in range(1, len(auto_report.objectives) + 1):
        if str(num) not in arg:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[7])
            return
    for idx, arg_num in enumerate(arg):
        arg_num = int(arg_num)
        for num, objective in enumerate(auto_report.objectives):
            if num + 1 == arg_num:
                if objective.startswith('event'):
                    new_order[f'event {idx + 1}'] = auto_report.objectives[f'event {num + 1}']
                else:
                    new_order[objective] = auto_report.objectives[objective]
    auto_report.objectives = new_order

    await purge_own_messages(CHANNEL_ADMIN)
    await auto_report.report_send()
    await purge_commands(CHANNEL_ADMIN)





# class HourlyReport:
#     def __init__(self, bot):
#         self.bot = bot
#         self.conflicts_active_order = OrderedDict()
#         self.message_start = f'Current objectives for {os.getenv("FACTION_NAME")}:\n\n'
#         self.comment = ''
#         self.event = {}
#         self.report_message_id = 0
#
#     def updated_ago_text(self, updated_at):
#         updated_at = frontier_tz.localize(datetime.strptime(updated_at[0:16], '%Y-%m-%dT%H:%M'))
#         updated_ago = str(frontier_time - updated_at)[:-13]
#         if (
#                 updated_ago[-2:] == '1' or
#                 updated_ago[-2:] == '21'
#         ):
#             text = f'{updated_ago} hour ago.'
#         elif updated_ago[-2:] == '0':
#             text = 'less than an hour ago.'
#         else:
#             text = f'{updated_ago} hours ago.'
#         return text
#
#     def report_pending(self, conflicts_pending):
#         text = ''
#         if len(conflicts_pending) == 0:
#             pass
#         else:
#             for conflict in conflicts_pending:
#                 state = conflicts_pending[conflict]["state"]
#                 text += f':arrow_up: - *Pending* {state.capitalize()} in {conflict}\n'
#
#                 if conflicts_pending[conflict]['win']:
#                     text += f'On victory we gain: *{conflicts_pending[conflict]["win"]}*\n'
#                 if conflicts_pending[conflict]['loss']:
#                     text += f'On defeat we lose: *{conflicts_pending[conflict]["loss"]}*\n'
#                 if not conflicts_pending[conflict]['win'] and not conflicts_pending[conflict]['loss']:
#                     text += '*No stakes*\n'
#
#                 updated_at = conflicts_pending[conflict]["updated_at"]
#                 updated_at_time = frontier_tz.localize(datetime.strptime(updated_at[0:16], '%Y-%m-%dT%H:%M'))
#                 if (frontier_time - updated_at_time) >= timedelta(hours=12):
#                     text += f'Last updated: **{self.updated_ago_text(updated_at)}**\n\n'
#                 else:
#                     text += f'Last updated: {self.updated_ago_text(updated_at)}\n\n'
#         self.report += text
#
#     def report_recovering(self, conflicts_recovering):
#         text = ''
#         if len(conflicts_recovering) == 0:
#             pass
#         else:
#             for conflict in conflicts_recovering:
#                 state = conflicts_recovering[conflict]["state"]
#                 status = conflicts_recovering[conflict]["status"]
#                 stake = conflicts_recovering[conflict]["stake"]
#                 text += f':arrow_down: - *Recovering* from {state.capitalize()} in {conflict} - {status.capitalize()}'
#                 if stake:
#                     if status == 'victory':
#                         text += f', we won *{stake}*\n\n'
#                     if status == 'defeat':
#                         text += f', we lost *{stake}*\n\n'
#                 else:
#                     text += '!\n\n'
#         self.report += text
#
#     def unvisited_systems_text(self, unvisited_systems):
#         text = 'Systems unchecked for:\n'
#         lines = 1
#         for day in unvisited_systems:
#             if unvisited_systems[day]:
#                 lines += 1
#                 if 5 <= day <= 6:
#                     text += f'**{day} days**: '
#                 elif day == 7:
#                     text += f':exclamation:**Over a week**: '
#                 else:
#                     text += f'{day} days: '
#                 text += ', '.join(unvisited_systems[day])
#                 text += '\n'
#         if lines == 1:
#             return
#         elif lines == 2:
#             text = text.replace(':\n', ' ')
#         self.report += text
#
#     async def report_send(self):
#         self.report = ''
#         start_num = len(self.event) + 1
#         self.report_active(self.cache.conflicts_active, start_num)
#         self.report_pending(self.cache.conflicts_pending)
#         self.report_recovering(self.cache.conflicts_recovering)
#         self.unvisited_systems_text(self.cache.unvisited_systems)
#
#         await purge_own_messages(CHANNEL_ADMIN)
#
#         report = self.message_start
#         if self.comment:
#             report += f'{self.comment}\n\n'
#         if self.event:
#             for ev in self.event:
#                 report += f'{number_emoji[ev]} - {self.event[ev]}\n\n'
#         report += self.report
#         await bot.get_channel(CHANNEL_ADMIN).send(report)
#
#     @tasks.loop(minutes=30)
#     async def report_loop(self):
#         await bot.get_channel(CHANNEL_ADMIN).send(f'`Updating report...`')
#         self.cache = Cache()
#         if self.cache.faction_data['error'] != 0:
#             await bot.get_channel(CHANNEL_ADMIN).send(errors_text[self.cache.faction_data['error']])
#             return
#         await self.report_send()
#
#         await purge_commands(CHANNEL_ADMIN)
#
#
# @bot.command(name='seen',
#              brief='Marks report as seen and removes highlights',
#              description='Marks report as seen and removes highlights')
# @commands.has_role(ADMIN_ROLE)
# async def seen(ctx):
#     for conflict in hr.conflicts_active_order:
#         hr.conflicts_active_order[conflict]['score_us'] = hr.cache.conflicts_active[conflict]['score_us']
#         hr.conflicts_active_order[conflict]['score_them'] = hr.cache.conflicts_active[conflict]['score_them']
#         hr.conflicts_active_order[conflict]['new'] = False
#
#     await hr.report_send()
#     await purge_commands(CHANNEL_ADMIN)
#
#
# @bot.command(name='faction',
#              brief='Changes the followed faction',
#              description='Changes the followed faction')
# @commands.has_role(ADMIN_ROLE)
# async def faction(ctx, *args):
#     await bot.get_channel(CHANNEL_ADMIN).send(f'`Changing faction...`')
#     os.environ['FACTION_NAME'] = string.capwords(' '.join(args))
#     hr.report_loop.cancel()     # object NoneType can't be used in 'await' expression
#     await asyncio.sleep(3)      # TODO: fix this with a proper await
#     await bot_start()


bot.run(TOKEN)
