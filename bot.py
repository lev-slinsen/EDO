import os
from collections import OrderedDict
from datetime import datetime

import discord
import pytz
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

from cache import Cache
from log import logEvent

# TODO: refactor LTD systems command
# TODO: add reaction mechanics
# TODO: add links to systems and stations on EDDB or Inara

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')
LOG = os.getenv('LOG')
CHANNEL_ADMIN = int(os.getenv('CHANNEL_ADMIN'))
ADMIN_ROLE = os.getenv('ADMIN_ROLE')

bot = commands.Bot(command_prefix='!')
client = discord.Client()

frontier_tz = pytz.timezone('UTC')
frontier_time = datetime.now(frontier_tz)

number_emoji = (':zero:', ':one:', ':two:', ':three:', ':four:', ':five:',
                ':six:', ':seven:', ':eight:', ':nine:', ':keycap_ten:')
errors_text = {1: '`No such faction. Please check faction name and try again.`',
               2: '`Unable to add comment to this objective. '
                  'Instead, try changing objective text with the "!event" command.`',
               3: '`There is no event to delete.`',
               4: '`There are multiple events, please select the one to delete with respective the number.`',
               5: '`Incorrect event selected for change.`',
               6: "`There's a different number of objectives, please try again.`",
               7: '`Typo?`',
               8: '`This message will self-update every 30 minutes. '
                  'Please mention outside of this report to avoid mention spam.`'}


'''What I do on startup'''


@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}')
    print()
    await bot_start()


'''What I can do on my own'''


async def bot_start():
    global auto_report
    auto_report = AutoReport(bot)
    auto_report.report_loop.start()


async def purge_own_messages(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=100).flatten():
        if message.author == bot.user:
            await message.delete()


async def purge_commands(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=100).flatten():
        if message.content.startswith('!'):
            await message.delete()


'''What I remember'''


class AutoReport:
    def __init__(self, bot):
        self.bot = bot
        self.objectives = OrderedDict()
        self.comment = ''
        self.report_message_id = 0
        await logEvent("AutoReport Init","") #start the log file

    @tasks.loop(minutes=30)
    async def report_loop(self):
        if DEBUG: print(f'{frontier_time}: report_loop start')
        if LOG : await logEvent("report_loop start","")
        await bot.get_channel(CHANNEL_ADMIN).send(f'`Updating report...`')
        self.cache = Cache()
        await self.cache.gather_data()
        if self.cache.faction_data['error'] != 0:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[self.cache.faction_data['error']])
            return
        await self.objectives_collect()
        await purge_own_messages(CHANNEL_ADMIN)
        await self.report_send()
        await purge_commands(CHANNEL_ADMIN)
        if DEBUG: print('report_loop done\n')
        if LOG: await logEvent("report_loop done","")

    async def objectives_collect(self):
        if DEBUG: print('objective_collect start')
        if LOG: await logEvent("objective_collect start","")
        await self.report_retreating(self.cache.retreating_systems)
        await self.report_active(self.cache.conflicts_active)
        await self.report_pending(self.cache.conflicts_pending)
        await self.report_recovering(self.cache.conflicts_recovering)
        if DEBUG: print('objective_collect done')
        if LOG: await logEvent("objective_collect done","")

    async def report_send(self):
        if DEBUG: print('report_send start')
        if LOG: await logEvent("report_send start","")

        reports = []
        
        if self.comment:
            reports.append(f'Current objectives for {os.getenv("FACTION_NAME")}:\n\n' + f'{self.comment}\n\n')
        else :
            reports.append(f'Current objectives for {os.getenv("FACTION_NAME")}:\n\n')

        for num, objective_active in enumerate(self.objectives):
            objective = self.objectives[objective_active]
            if objective.status == 'active' and objective.state == 'retreat' :
                if DEBUG : print(f'retreating_systems_text for {objective_active} start')
                if LOG: await logEvent("retreating_systems_text start",f"{objective_active}")
                reports.append( await objective.retreating_systems_text(num+1, objective_active) )
                if DEBUG : print(f'retreating_systems_text for {objective_active} done')
                if LOG : await logEvent("retreating_systems_text done",f"{objective_active}")
            elif objective.status == 'active':
                if DEBUG: print(f'conflict_active_text for {objective_active} start')
                if LOG: await logEvent("conflict_active_text start",f"{objective_active}")
                reports.append( await objective.conflict_active_text(num + 1, objective_active) )
                if DEBUG: print(f'conflict_active_text for {objective_active} done')
                if LOG: await logEvent("conflict_active_text done",f"{objective_active}")
            elif objective.status == 'event':
                if DEBUG: print(f'conflict_active_text for event #{num + 1} start')
                if LOG: await logEvent("conflict_active_text start",f"{num+1}")
                reports.append( f'{number_emoji[num + 1]} {objective.text}\n\n' )
                if DEBUG: print(f'conflict_active_text for event #{num + 1} done')
                if LOG: await logEvent("conflict_active_text done",f"{num+1}")

        for objective_pending in self.objectives:
            objective = self.objectives[objective_pending]
            if objective.status == 'pending' and objective.state=='retreat' :
                if DEBUG : print(f'retreating_systems_text for {objective_pending} start')
                if LOG: await logEvent("retreating_systems_text start",f"{objective_pending}")
                reports.append( await objective.retreating_systems_text(num+1, objective_pending) )
                if DEBUG : print(f'retreating_systems_text for {objective_pending} done')
                if LOG: await logEvent("retreating_systems_text done",f"{objective_pending}")
            elif objective.status == 'pending':
                if DEBUG: print(f'conflict_pending_text for {objective_pending} start')
                if LOG: await logEvent("conflict_pending_text start",f"{objective_pending}")
                reports.append( await objective.conflict_pending_text(objective_pending) )
                if DEBUG: print(f'conflict_pending_text for {objective_pending} done')
                if LOG: await logEvent("conflict_pending_text done",f"{objective_pending}")

        for objective_recovering in self.objectives:
            objective = self.objectives[objective_recovering]
            if objective.status=="recovering" and objective.state=="retreat" :
                if DEBUG : print(f'retreating_systems_text for {objective_recovering} start')
                if LOG : await logEvent("retreating_systems_text start",f"{objective_recovering}")
                reports.append( await objective.retreating_systems_text(num+1, objective_recovering) )
                if DEBUG : print(f'retreating_systems_text for {objective_recovering} done')
                if LOG : await logEvent("retreating_systems_text done",f"{objective_recovering}")
            elif objective.status == 'victory' or objective.status == 'defeat':
                if DEBUG: print(f'conflict_recovering_text for {objective_recovering} start')
                if LOG: await logEvent("conflict_recovering_text start",f"{objective_recovering}")
                reports.append( await objective.conflict_recovering_text(objective_recovering) )
                if DEBUG: print(f'conflict_recovering_text for {objective_recovering} done')
                if LOG: await logEvent("conflict_recovering_text done",f"{objective_recovering}")

        reports.append( await self.unvisited_systems(self.cache.unvisited_systems) )

        for report in reports :
            await bot.get_channel(CHANNEL_ADMIN).send(report)

        if DEBUG: print('report_send done')
        if LOG: await logEvent("report_send done","")

    async def report_retreating(self, retreating_systems) : #retreating_systems is my report from cache
        if DEBUG : print('report_retreating start')
        if LOG : await logEvent("report_retreating start","")
        for old_objective in self.objectives :
            if ( old_objective not in retreating_systems ): #if the old objective matches one of the ones that exists now
                self.objectives.pop(old_objective) #remove it
        for retreating_system in retreating_systems : #for every current retreating system
            if (retreating_system not in old_objective) : #if it doesn't already exist
                self.objectives[retreating_system] = Objective()
                objective = self.objectives[retreating_system]
                objective.status = retreating_systems[retreating_system]["status"]
                objective.state = 'retreat'
                objective.influence = retreating_systems[retreating_system]["influence"]
                objective.updated_ago = retreating_systems[retreating_system]["updated_ago"]
        if DEBUG : print('report_retresting done')
        if LOG : await logEvent("report_retreating done","")

    async def report_active(self, conflicts_active):
        if DEBUG: print('report_active start')
        if LOG : await logEvent("report_active start","")
        for old_objective in self.objectives:
            if self.objectives[old_objective].status == 'active' and old_objective not in conflicts_active:
                self.objectives.pop(old_objective)
        for conflict in conflicts_active:
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
                objective.updated_ago = conflicts_active[conflict]['updated_ago']
            else:
                objective = self.objectives[conflict]
                objective.status = 'active'
                if objective.score_us != conflicts_active[conflict]['score_us']:
                    objective.new.append('score_us')
                    if 'score_them' in objective.new:
                        objective.new.remove('score_them')
                if objective.score_them != conflicts_active[conflict]['score_them']:
                    objective.new.append('score_them')
                    if 'score_us' in objective.new:
                        objective.new.remove('score_us')
                objective.score_us = conflicts_active[conflict]['score_us']
                objective.score_them = conflicts_active[conflict]['score_them']
                objective.updated_ago = conflicts_active[conflict]['updated_ago']
        if DEBUG: print('report_active done')
        if LOG : await logEvent("report_active done","")

    async def report_pending(self, conflicts_pending):
        if DEBUG: print('report_pending start')
        if LOG : await logEvent("report_pending start","")
        for old_objective in self.objectives:
            if self.objectives[old_objective].status == 'pending' and old_objective not in conflicts_pending:
                self.objectives.pop(old_objective)
        for conflict in conflicts_pending:
            if conflict not in self.objectives:
                self.objectives[conflict] = Objective()
                objective = self.objectives[conflict]
                objective.status = 'pending'
                objective.state = conflicts_pending[conflict]['state']
                objective.opponent = conflicts_pending[conflict]['opponent']
                objective.win = conflicts_pending[conflict]['win']
                objective.loss = conflicts_pending[conflict]['loss']
                objective.updated_ago = conflicts_pending[conflict]['updated_ago']
            else:
                objective = self.objectives[conflict]
                objective.updated_ago = conflicts_pending[conflict]['updated_ago']
        if DEBUG: print('report_pending done')
        if LOG : await logEvent("report_pending done","")

    async def report_recovering(self, conflicts_recovering):
        if DEBUG: print('report_recovering start')
        if LOG : await logEvent("report_recovering start","")
        for old_objective in self.objectives:
            if (
                    (self.objectives[old_objective].status == 'defeat' or
                     self.objectives[old_objective].status == 'victory') and
                    old_objective not in conflicts_recovering
            ):
                self.objectives.pop(old_objective)
        for conflict in conflicts_recovering:
            if conflict not in self.objectives:
                self.objectives[conflict] = Objective()
                objective = self.objectives[conflict]
                objective.status = conflicts_recovering[conflict]['status']
                objective.state = conflicts_recovering[conflict]['state']
                objective.win = conflicts_recovering[conflict]['stake']
                objective.updated_ago = conflicts_recovering[conflict]['updated_ago']
            else:
                objective = self.objectives[conflict]
                objective.updated_ago = conflicts_recovering[conflict]['updated_ago']
        if DEBUG: print('report_recovering done')
        if LOG : await logEvent("report_recovering done","")

    async def unvisited_systems(self, unvisited_systems):
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
            return ''
        elif lines == 2:
            text = text.replace(':\n', ' ')
        return text


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
        self.new = []
        self.influence = ''

    async def retreating_systems_text(self, num, system_name) :
        text =  '{0} {1} in **{2}**\n> Influence: {3}'.format(number_emoji[num], self.state.capitalize(), system_name, self.influence)
        text += f'Updated {self.updated_ago}.\n\n'
        return text

    async def conflict_active_text(self, num, system_name):
        text = '{0} {1} in **{2}**\n' \
               '> {3} [ {4} - {5} ] {6}\n'.format(
                number_emoji[num],
                self.state.capitalize(),
                system_name,
                os.getenv("FACTION_NAME"),
                self.score_us,
                self.score_them,
                self.opponent
                )
        if self.win:
            text += f'> On victory we gain: *{self.win}*\n'
        if self.loss:
            text += f'> On defeat we lose: *{self.loss}*\n'
        if not self.win and not self.loss:
            text += '> *No stakes*\n'
        text += f'Updated {self.updated_ago}.\n'
        if self.comment:
            text += f'\n{self.comment}\n\n'
        else:
            text += '\n'
        return text

    async def conflict_pending_text(self, system_name):
        text = f':arrow_up: *Pending* {self.state} in {system_name}.\n' \
               f'> Opponent: {self.opponent}\n'
        if self.win:
            text += f'> On victory we gain: *{self.win}*\n'
        if self.loss:
            text += f'> On defeat we lose: *{self.loss}*\n'
        if not self.win and not self.loss:
            text += '> *No stakes*\n'
        text += f'Updated {self.updated_ago}.\n\n'
        return text

    async def conflict_recovering_text(self, system_name):
        text = f':arrow_down: *Recovering* from {self.state} in {system_name}.\n'
        if self.status == 'victory':
            if self.win:
                text += f'> We won *{self.win}*\n\n'
            else:
                text += '> We won!\n\n'
        elif self.status == 'defeat':
            if self.win:
                text += f'> We lost *{self.win}*\n\n'
            else:
                text += '> We lost!\n\n'
        return text


'''Commands I understand'''


@bot.command(name='comment',
             brief='Adds comments to the report or objectives',
             description='!comment [your_text] - Adds text at the top of the report.\n'
                         '!comment - Removes general comment\n'
                         '!comment [objective_number] [your_text] - Adds comment to the specified objective.\n'
                         '!comment [objective_number] - Removes an objective comment.\n'
                         'To add multiple lines, wrap comment text into "".')
@commands.has_role(ADMIN_ROLE)
async def comment(ctx, arg_num=None, *args):
    if '<@' in arg_num:
        await bot.get_channel(CHANNEL_ADMIN).send(errors_text[8])
        return
    for arg in args:
        if '<@' in arg:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[8])
            return
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
             description='!event [your_text] - Adds a new custom objective.\n'
                         '!event [objective_number] [your_text] - Changes text for the specified objective.\n'
                         '!event - Removes the custom objective, but only if there is only one.\n'
                         '!event [objective_number] - Removes the specified custom objective.\n'
                         'To add multiple lines, wrap objective text into "".')
@commands.has_role(ADMIN_ROLE)
async def event(ctx, arg_num=None, *args):
    if '<@' in arg_num:
        await bot.get_channel(CHANNEL_ADMIN).send(errors_text[8])
        return
    for arg in args:
        if '<@' in arg:
            await bot.get_channel(CHANNEL_ADMIN).send(errors_text[8])
            return
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


# @bot.command(name='ltd')
# async def ltd(ctx):
#     if len(auto_report.cache.ltd_systems) == 0:
#         text = '`No suitable systems at this moment`'
#     else:
#         text = 'Best places to sell your :gem:\n'
#         for system in auto_report.cache.ltd_systems:
#             text += f'**{system}**:'
#             for station in auto_report.cache.ltd_systems[system]:
#                 if len(auto_report.cache.ltd_systems[system]) == 1:
#                     text += f" {station['name']} ({station['type']}) - {station['distance']} Ls, {station['distFromBoran']} Lys from Borann."
#                 else:
#                     text += f"\n> {station['name']} ({station['type']}) - {station['distance']} Ls, {station['distFromBoran']} Lys from Borann."
#             text += '\n'
#
#     await ctx.channel.send(text)
#     await purge_commands(ctx.channel.id)


# @bot.event
# async def on_message(message):
#     if (
#             message.author == bot.user and
#             auto_report.message_start in message.content
#     ):
#         global report_message_id
#         report_message_id = message.id
#     await bot.process_commands(message)


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
