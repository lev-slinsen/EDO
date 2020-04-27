import datetime
import gc
import os
from collections import OrderedDict

import discord
from discord.ext import commands
from discord.ext import tasks
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

number_emoji = (':zero:', ':one:', ':two:', ':three:', ':four:', ':five:',
                ':six:', ':seven:', ':eight:', ':nine:', ':ten:')


'''What I do on startup'''


@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}\n')

    global hr
    hr = HourlyReport(bot)
    hr.report_loop.start()


'''What I can do on my own'''


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
    for obj in gc.get_objects():
        if isinstance(obj, HourlyReport):
            if (
                    message.author == bot.user and
                    obj.message_start in message.content
            ):
                global report_message_id
                report_message_id = message.id
    await bot.process_commands(message)


class HourlyReport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conflicts_active_order = OrderedDict()
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
        self.report = ''

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

                    num = number_emoji[idx+1]

                    self.report += '{0} - {1} in {2}\n' \
                                   '{3} [ {4} - {5} ] {6}\n'.format(
                                    num,
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

    async def report_print(self):
        cache = self.cache
        self.report_active(cache)
        self.report_recovering(cache)
        self.report_pending(cache)

        await purge_own_messages(CHANNEL_ADMIN)

        if self.comment == '':
            await bot.get_channel(CHANNEL_ADMIN).send(f'{self.message_start}{self.report}')
        else:
            await bot.get_channel(CHANNEL_ADMIN).send(f'{self.message_start}{self.comment}\n\n{self.report}')

    @tasks.loop(minutes=30)
    async def report_loop(self):
        self.cache = Cache()
        await self.report_print()


'''Commands I understand'''


@bot.command(name='comment',
             brief='Adds comment to the report, wrap it into "".',
             description='Adds comment to the report, use wrap it into "".')
@commands.has_role(ADMIN_ROLE)
async def comment(ctx, arg):
    hr.comment = arg

    await hr.report_print()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='reorder',
             brief='Reorders active conflicts. Use a set of numbers with no spaces.',
             description='Reorders active conflicts. Use a set of numbers with no spaces.')
@commands.has_role(ADMIN_ROLE)
async def reorder(ctx, arg):
    new_order = OrderedDict()
    if len(arg) != len(hr.conflicts_active_order):
        await bot.get_channel(CHANNEL_ADMIN).send(f'Learn how to count, noob!')
        return

    for num in range(1, len(hr.conflicts_active_order)+1):
        if str(num) not in arg:
            await bot.get_channel(CHANNEL_ADMIN).send(f'Numbers, motherfucker, do you speak it?')
            return

    for num in arg:
        for idx, conflict in enumerate(hr.conflicts_active_order):
            if idx+1 == int(num):
                new_order[conflict] = hr.conflicts_active_order[conflict]
    hr.conflicts_active_order = new_order

    await hr.report_print()
    await purge_commands(CHANNEL_ADMIN)


@bot.command(name='seen',
             brief='Marks report as seen and removes highlights.',
             description='Marks report as seen and removes highlights.')
@commands.has_role(ADMIN_ROLE)
async def seen(ctx):
    for conflict in hr.conflicts_active_order:
        hr.conflicts_active_order[conflict]['score_us'] = hr.cache.conflicts_active[conflict]['score_us']
        hr.conflicts_active_order[conflict]['score_them'] = hr.cache.conflicts_active[conflict]['score_them']
        hr.conflicts_active_order[conflict]['updated_ago'] = hr.cache.conflicts_active[conflict]['updated_ago']
        hr.conflicts_active_order[conflict]['new'] = False

    await hr.report_print()
    await purge_commands(CHANNEL_ADMIN)


bot.run(TOKEN)
