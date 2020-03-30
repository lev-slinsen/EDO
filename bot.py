import os
import datetime
import asyncio
import time

from discord.ext import commands
from discord.ext.commands import CommandNotFound
from dotenv import load_dotenv

from eddb_api import faction_update, conflicts

load_dotenv()
# All environment variables are stored in '.env' file
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')

bot = commands.Bot(command_prefix='')


"""
EVENTS
"""


@bot.event
# What I do on startup
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}\n')
    while True:
        faction_update()
        print(conflicts())
        time.sleep(3600)


"""
ERRORS
"""


@bot.event
# Hides 'command not found' errors in console
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    raise error


@bot.event
# Logs command errors into 'err.log' file
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have required role for this command.')
        with open('EDO/err.log', 'a+') as err_log:
            print(f'{datetime.datetime.now()}, User: {ctx.author}\n'
                  f'Command: {ctx.command}, Error: Role check failure\n')
            err_log.write(f'{datetime.datetime.now()}, User: {ctx.author}\n'
                          f'Command: {ctx.command}, Error: Role check failure\n')


bot.run(TOKEN)
