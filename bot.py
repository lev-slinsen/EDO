import os
import datetime
import asyncio

from discord.ext import commands
from discord.ext.commands import CommandNotFound
from dotenv import load_dotenv

from eddb_api import Cache

load_dotenv()
# All environment variables are stored in '.env' file
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')
FACTION_NAME = os.getenv('FACTION_NAME')

bot = commands.Bot(command_prefix='!')


@bot.event
# What I do on startup
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}\n')
    while True:
        global cache
        cache = Cache()
        await asyncio.sleep(3600)


@bot.command(name='active', help='Shows active conflicts')
async def conflicts_active_cmd(ctx):
    # reply = ''
    if len(cache.conflicts_active) == 0:
        await ctx.send(f'Our kingdom is at peace!')
        return
    else:
        reply = f'Active conflicts: {len(cache.conflicts_active)}'
        for idx, conflict in enumerate(cache.conflicts_active):
            conflict_id = conflict
            details = cache.conflicts_active[conflict]
            system = details['system']
            state = details['state']
            enemy = details['enemy']
            score = details['score']
            win = details['win']
            if win is None:
                win = 'Nothing'
            loss = details['loss']
            if loss is None:
                loss = 'Nothing'
            reply += f'\n{conflict_id}: {state} in {system}' \
                     f'\n{FACTION_NAME} {score} {enemy}' \
                     f'\nOn win we get: {win}' \
                     f'\nOn defeat we lose: {loss}'
        print(reply)
        await ctx.send(reply)


@bot.event
# Hides 'command not found' errors in console
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    raise error


@bot.event
# Logs errors into 'err.log' file
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have required role for this command.')
        with open('EDO/err.log', 'a+') as err_log:
            print(f'{datetime.datetime.now()}, User: {ctx.author}\n'
                  f'Command: {ctx.command}, Error: Role check failure\n')
            err_log.write(f'{datetime.datetime.now()}, User: {ctx.author}\n'
                          f'Command: {ctx.command}, Error: Role check failure\n')


bot.run(TOKEN)
