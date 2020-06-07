import os
from collections import OrderedDict

import discord
from discord.ext import commands
from discord.ext import tasks

import settings as s
from cache import Cache
from decorators import bug_catcher

# TODO: check for number of symbols in report (max 2000)
# TODO: add reaction mechanics
# TODO: add links to systems and stations on EDDB or Inara
# TODO: add retreat tracking
# TODO: add ignore command to delete unwanted system from objectives
# TODO: put LTD systems report on a different, less frequent loop
# TODO: allow user log download

log_dev = s.logger_dev.logger
log_usr = s.logger_usr.logger

bot = commands.Bot(command_prefix='!')
client = discord.Client()

'''What I do on startup'''


@bot.event
@bug_catcher
async def on_ready():
    log_dev.debug(f"{'-' * 20} {bot.user.name} is alive!")
    log_usr.debug(f"{'-' * 20} {bot.user.name} is alive!")
    for guild in bot.guilds:
        if guild.name is None:
            log_dev.critical(f'problem retrieving a guild')
            return
    global auto_report
    auto_report = AutoReport(bot)
    auto_report.report_loop.start()


'''My primary job'''


class AutoReport:
    def __init__(self, bot):
        self.bot = bot
        self.objectives = OrderedDict()
        self.comment = ''
        self.report_message_id = 0

    @tasks.loop(minutes=30)
    @bug_catcher
    async def report_loop(self):
        log_dev.debug(f"{'-' * 20}start")
        await bot.get_channel(s.CHANNEL_ADMIN).send(f'`Updating report...`')
        self.cache = Cache()
        await self.cache.gather_data()
        if self.cache.faction_data['error'] != 0:
            await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[self.cache.faction_data['error']])
            return
        await self.objectives_collect()
        await purge_own_messages(s.CHANNEL_ADMIN)
        await self.report_send()
        await purge_commands(s.CHANNEL_ADMIN)
        log_dev.debug(f"{'-' * 20}finish")

    @bug_catcher
    async def objectives_collect(self):
        await self.report_pending(self.cache.conflicts_pending)
        await self.report_active(self.cache.conflicts_active)
        await self.report_recovering(self.cache.conflicts_recovering)

    @bug_catcher
    async def report_pending(self, conflicts_pending):
        for old_objective in self.objectives:
            if self.objectives[old_objective].status == 'pending' and old_objective not in conflicts_pending:
                self.objectives.pop(old_objective)
                log_usr.info(f'{self.objectives[old_objective].state} in {old_objective} is no longer pending')

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

                log_msg = f'pending {objective.state} in {conflict}, opponent: {objective.opponent}'
                if objective.win:
                    log_msg += f', win stake: {objective.win}'
                if objective.loss:
                    log_msg += f', loss stake: {objective.loss}'
                log_usr.info(log_msg)
            else:
                objective = self.objectives[conflict]
                objective.updated_ago = conflicts_pending[conflict]['updated_ago']
        log_dev.debug('finished successfully')

    @bug_catcher
    async def report_active(self, conflicts_active):
        for old_objective in self.objectives:
            if self.objectives[old_objective].status == 'active' and old_objective not in conflicts_active:
                self.objectives.pop(old_objective)
                log_usr.info(f'{self.objectives[old_objective].state} in {old_objective} is no longer active')

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

                log_msg = f'{objective.state} in now active in {conflict}, opponent: {objective.opponent}'
                if objective.win:
                    log_msg += f', win stake: {objective.win}'
                if objective.loss:
                    log_msg += f', loss stake: {objective.loss}'
                log_usr.info(log_msg)
            else:
                objective = self.objectives[conflict]

                if objective.status != 'active':
                    objective.status = 'active'
                    log_usr.info(f'{objective.state} in {objective} in now active')

                if objective.score_us != conflicts_active[conflict]['score_us']:
                    log_usr.info(f"our score in {objective} {objective.state} "
                                 f"changed from {objective.score_us} to {conflicts_active[conflict]['score_us']}")

                    objective.new.append('score_us')
                    objective.score_us = conflicts_active[conflict]['score_us']
                    if 'score_them' in objective.new:
                        objective.new.remove('score_them')

                if objective.score_them != conflicts_active[conflict]['score_them']:
                    log_usr.info(f"opponent's score in {objective} {objective.state} "
                                 f"changed from {objective.score_them} to {conflicts_active[conflict]['score_them']}")

                    objective.score_them = conflicts_active[conflict]['score_them']
                    objective.new.append('score_them')
                    if 'score_us' in objective.new:
                        objective.new.remove('score_us')
            objective.updated_ago = conflicts_active[conflict]['updated_ago']
        log_dev.debug('finished successfully')

    @bug_catcher
    async def report_recovering(self, conflicts_recovering):
        for old_objective in self.objectives:
            if (
                    self.objectives[old_objective].status in ('defeat', 'victory') and
                    old_objective not in conflicts_recovering
            ):
                self.objectives.pop(old_objective)
                log_usr.info(f"we're no longer recovering from "
                             f"{self.objectives[old_objective].state} in {old_objective}")

        for conflict in conflicts_recovering:
            if conflict not in self.objectives:
                self.objectives[conflict] = Objective()
                objective = self.objectives[conflict]
                objective.status = conflicts_recovering[conflict]['status']
                objective.state = conflicts_recovering[conflict]['state']
                objective.win = conflicts_recovering[conflict]['stake']
                objective.updated_ago = conflicts_recovering[conflict]['updated_ago']

                log_msg = f'recovering from {objective.state} in {conflict}'
                if objective.status == 'victory':
                    log_msg += f', we won: {objective.win}'
                elif objective.status == 'defeat':
                    log_msg += f', we lost: {objective.win}'
                log_usr.info(log_msg)
            else:
                objective = self.objectives[conflict]
                objective.updated_ago = conflicts_recovering[conflict]['updated_ago']
        log_dev.debug('finished successfully')

    @bug_catcher
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

        log_dev.debug('finished successfully')
        return text

    @bug_catcher
    async def report_send(self):
        report = f'Current objectives for {os.getenv("FACTION_NAME")}:\n\n'

        if self.comment:
            report += f'{self.comment}\n\n'

        num = 1
        for objective_active in self.objectives:
            objective = self.objectives[objective_active]
            if objective.status == 'active':
                report += await objective.conflict_active_text(num, objective_active)
                num += 1
            elif objective.status == 'event':
                report += f'{s.number_emoji[num]} {objective.text}\n\n'
                num += 1

        for objective_pending in self.objectives:
            objective = self.objectives[objective_pending]
            if objective.status == 'pending':
                report += await objective.conflict_pending_text(objective_pending)

        for objective_recovering in self.objectives:
            objective = self.objectives[objective_recovering]
            if objective.status in ('victory', 'defeat'):
                report += await objective.conflict_recovering_text(objective_recovering)

        report += await self.unvisited_systems(self.cache.unvisited_systems)

        await bot.get_channel(s.CHANNEL_ADMIN).send(report)
        log_dev.debug('finished successfully')


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

    @bug_catcher
    async def conflict_active_text(self, num, system_name):
        text = '{0} {1} in **{2}**\n' \
               '> {3} [ {4} - {5} ] {6}\n'.format(
            s.number_emoji[num],
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

    @bug_catcher
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

    @bug_catcher
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
@commands.has_role(s.ADMIN_ROLE)
@bug_catcher
async def comment(ctx, arg_num='', *args):
    if await detect_mention(args + (arg_num,)):
        return

    # Deletes general comment
    if not arg_num:
        auto_report.comment = ''
        log_usr.info('general comment removed')

    # Adds objective comment
    elif arg_num.isnumeric():
        arg_num = int(arg_num) - 1
        if 1 <= arg_num + 1 <= len(auto_report.objectives):
            for num, objective in enumerate(auto_report.objectives):
                if int(arg_num) == num:
                    objective_data = auto_report.objectives[objective]
                    if objective_data.status != 'active':
                        await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[2])
                        return
                    else:
                        objective_data.comment = (' '.join(args))
                        log_usr.info(f'{objective_data.state} in {objective} comment updated: {objective_data.comment}')
        else:
            await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[2])
            return

    # Adds general comment
    else:
        text = f'{arg_num} ' + (' '.join(args))
        auto_report.comment = text
        log_usr.info(f'new general comment: {text}')

    await purge_own_messages(s.CHANNEL_ADMIN)
    await auto_report.report_send()
    await purge_commands(s.CHANNEL_ADMIN)


@bot.command(name='event',
             brief='Adds event to the report',
             description='!event [your_text] - Adds a new custom objective.\n'
                         '!event [objective_number] [your_text] - Changes text for the specified objective.\n'
                         '!event - Removes the custom objective, but only if there is only one.\n'
                         '!event [objective_number] - Removes the specified custom objective.\n'
                         'To add multiple lines, wrap objective text into "".')
@commands.has_role(s.ADMIN_ROLE)
@bug_catcher
async def event(ctx, arg_num='', *args):
    async def log_text(text, message):
        if '\n' in text:
            text = '\n' + text
        log_usr.info(f"{message}{text}")

    if await detect_mention(args + (arg_num,)):
        return

    objectives = auto_report.objectives

    # Deletes an event
    if not arg_num:
        count = 0
        for objective in objectives:
            if objective.startswith('event'):
                count += 1
        if count <= 0:
            await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[3])
            return
        elif count >= 2:
            await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[4])
            return
        else:
            for objective in objectives:
                if objective.startswith('event'):
                    await log_text(objectives[objective].text, 'event deleted: ')
                    objectives.pop(objective)

    # Updates a specific event
    elif arg_num.isnumeric():
        changed = 0
        for num, objective in enumerate(objectives):
            if objective == f'event {arg_num}':
                await log_text(objectives[objective].text, 'event deleted: ')
                objectives[objective].text = (' '.join(args))
                await log_text(objectives[objective].text, 'new event: ')
                changed += 1
        if changed == 0:
            await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[5])
            return

        # Deletes a specific event
        if not args:
            await log_text(objectives[f'event {arg_num}'].text, 'event deleted: ')
            objectives.pop(f'event {arg_num}')

    # Adds a new event at the end of the list of objectives
    else:
        actives = 1
        for objective in objectives:
            if objectives[objective].status == 'active':
                actives += 1
        objectives[f'event {actives}'] = Objective()
        objective = objectives[f'event {actives}']
        objective.status = 'event'
        objective.text = f'{arg_num} ' + (' '.join(args))

    await purge_own_messages(s.CHANNEL_ADMIN)
    await auto_report.report_send()
    await purge_commands(s.CHANNEL_ADMIN)


@bot.command(name='order',
             brief='Puts objectives in a different order',
             description='Puts objectives in a different order. Pass a set of numbers with no spaces.')
@commands.has_role(s.ADMIN_ROLE)
@bug_catcher
async def order(ctx, arg):
    new_order = OrderedDict()
    if len(arg) != len(auto_report.objectives):
        await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[6])
        return
    for num in range(1, len(auto_report.objectives) + 1):
        if str(num) not in arg:
            await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[7])
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
    log_usr.info('objectives order changes')

    await purge_own_messages(s.CHANNEL_ADMIN)
    await auto_report.report_send()
    await purge_commands(s.CHANNEL_ADMIN)


@bot.command(name='ltd')
@bug_catcher
async def ltd(ctx):
    text = 'Best places to sell your :gem: (systems with best price are marked with :star:)\n'
    if len(auto_report.cache.ltd_systems) == 0:
        text = '`No suitable systems at this moment`'
    else:
        for distance in auto_report.cache.ltd_systems:
            system = auto_report.cache.ltd_systems[distance]
            system_name = system['system_name']
            if system['state'] == 'public_holiday':
                system_name += ' :star:'
            if len(auto_report.cache.ltd_systems) == 1:
                text = f"There's a single suitable system: **{system['system_name']}** " \
                       f"over {distance} Ly from HQ, last updated {system['updated_ago']}\n"
            else:
                text += f"{distance} Ly | **{system['system_name']}** | {system['updated_ago']}.\n"

    await ctx.channel.send(text)
    await purge_commands(ctx.channel.id)


'''Message managing tools'''


@bug_catcher
async def purge_own_messages(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=100).flatten():
        if message.author == bot.user:
            await message.delete()


@bug_catcher
async def purge_commands(channel_to):
    for message in await bot.get_channel(channel_to).history(limit=100).flatten():
        if message.content.startswith('!'):
            await message.delete()


@bug_catcher
async def detect_mention(args):
    for arg in args:
        if '<@' in arg:
            await bot.get_channel(s.CHANNEL_ADMIN).send(s.errors_text[8])
            return True
        else:
            return False


bot.run(s.TOKEN)
