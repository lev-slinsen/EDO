import asyncio
import datetime
import json
import os
import copy

from discord.ext import commands
from discord.ext.commands import CommandNotFound
from dotenv import load_dotenv

from eddb_api import Cache

load_dotenv()       # All environment variables are stored in '.env' file
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')
FACTION_NAME = os.getenv('FACTION_NAME')
CHANNEL_ADMIN = int(os.getenv('CHANNEL_ADMIN'))
CHANNEL_USER = int(os.getenv('CHANNEL_USER'))

bot = commands.Bot(command_prefix='!')

global cache
global conflicts_active
conflicts_active = {}


'''What I do on startup'''


@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}\n')
    cache_old = ''
    while True:     # Updates cache on startup and then every hour
        cache = Cache()
        if DEBUG:
            print('"Cached active conflicts":', cache.conflicts_active)
        if cache != cache_old:
            await purge(CHANNEL_ADMIN)
            for system in cache.conflicts_active:
                details = cache.conflicts_active[system]
                if system not in conflicts_active:
                    conflicts_active[system] = ConflictActive(
                        details['state'],
                        details['updated_at'],
                        details['enemy'],
                        details['score_us'],
                        details['score_them'],
                        details['win'],
                        details['loss']
                    )
                if system in conflicts_active:
                    if (conflicts_active[system].updated_at != details['updated_at']
                            and 'updated_at' not in conflicts_active[system].unseen):
                        conflicts_active[system].unseen.append('updated_at')
                    if (conflicts_active[system].score_us != details['score_us']
                            and 'score_us' not in conflicts_active[system].unseen):
                        conflicts_active[system].unseen.append('score_us')
                    if (conflicts_active[system].score_them != details['score_them']
                            and 'score_them' not in conflicts_active[system].unseen):
                        conflicts_active[system].unseen.append('score_them')
                print("TEST", conflicts_active[system])
        await asyncio.sleep(10)
        cache_old = copy.deepcopy(cache)


'''What I can do on my own'''


async def purge(channel_to):
    channel = bot.get_channel(channel_to)
    await channel.purge()


'''What I remember'''


class ConflictActive:
    def __init__(self, state, updated_at, enemy, score_us, score_them, win, loss):
        self.state = state
        self.updated_at = updated_at
        self.enemy = enemy
        self.score_us = score_us
        self.score_them = score_them
        self.win = win
        self.loss = loss
        self.unseen = ()

    def update(self):
        pass

    def report(self):
        pass


class ConflictOrder:
    def __init__(self, order):
        self.order = order

    def __call__(self):
        return self.order


async def send_report(channel_to):
    if len(cache.conflicts_active) == 0:
        await bot.get_channel(channel_to).send(f'Our kingdom is at peace!')
        return
    report = f'Conflicts status for {FACTION_NAME}:\n\n' \
             f'Active conflicts: {len(cache.conflicts_active)}\n'
    for conflict in cache.conflicts_active:
        details = cache.conflicts_active[conflict]
        system = conflict
        state = details['state']
        enemy = details['enemy']
        score_us = details['score_us']
        score_them = details['score_them']
        win = details['win']
        loss = details['loss']
        report += f'\n{conflict}: {state.capitalize()} in {system}.\n' \
                  f'{FACTION_NAME} dominated the conflict for {score_us} days ' \
                  f'and {enemy} dominated for {score_them} days.\n'
        if win != '':
            report += f'On win we get: {win}\n'
        if loss != '':
            report += f'On defeat we lose: {loss}\n'
    await bot.get_channel(channel_to).send(report)


'''Commands I understand'''


# @bot.command(name='active', help='I will show active conflicts')
# async def conflicts_active_cmd(ctx):
#     await send_report(ctx.channel.id)


'''How I handle errors'''


@bot.event
async def on_command_error(ctx, error):         # Hides 'command not found' errors in console
    if isinstance(error, CommandNotFound):
        return
    raise error


@bot.event
async def on_command_error(ctx, error):         # Logs errors into 'err.log' file
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have required role for this command.')
        with open('EDO/err.log', 'a+') as err_log:
            print(f'{datetime.datetime.now()}, User: {ctx.author}\n'
                  f'Command: {ctx.command}, Error: Role check failure\n')
            err_log.write(f'{datetime.datetime.now()}, User: {ctx.author}\n'
                          f'Command: {ctx.command}, Error: Role check failure\n')


bot.run(TOKEN)
