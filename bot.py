import asyncio
import datetime
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


'''What I do on startup'''


@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected to the following guilds:')
    for guild in bot.guilds:
        print(f'"{guild.name}" with id: {guild.id}\n')
    cache_old = ''
    while True:     # Updates cache on startup and then every hour
        global cache
        cache = Cache()
        if cache != cache_old:
            await send_report()
        await asyncio.sleep(3600)
        cache_old = copy.deepcopy(cache)


'''What I do on my own'''


async def send_report():
    if len(cache.conflicts_active) == 0:
        await bot.get_channel(CHANNEL_ADMIN).send(f'Our kingdom is at peace!')
        return
    report = f"""
Conflicts status for EIC:

Active conflicts: {len(cache.conflicts_active)}"""
    for conflict in cache.conflicts_active:
        conflict_id = conflict
        details = cache.conflicts_active[conflict]
        system = details['system']
        state = details['state']
        enemy = details['enemy']
        score_us = details['score_us']
        score_them = details['score_them']
        win = details['win']
        loss = details['loss']
        report += f"""

{conflict_id}: {state} in {system}.
{FACTION_NAME} dominated the conflict for {score_us} days and {enemy} dominated for {score_them} days."""
        if win != '':
            report += f'On win we get: {win}'
        if loss != '':
            report += f'On defeat we lose: {loss}'
    await bot.get_channel(CHANNEL_ADMIN).send(report)


'''Commands I understand'''


@bot.command(name='active', help='I will show active conflicts')
async def conflicts_active_cmd(ctx):
    if len(cache.conflicts_active) == 0:
        await ctx.send(f'Our kingdom is at peace!')
        return
    else:
        reply = f'Active conflicts: {len(cache.conflicts_active)}'
        f"""
Conflicts status for EIC:

Active conflicts: {len(cache.conflicts_active)}"""
        for conflict in cache.conflicts_active:
            conflict_id = conflict
            details = cache.conflicts_active[conflict]
            system = details['system']
            state = details['state']
            enemy = details['enemy']
            score_us = details['score_us']
            score_them = details['score_them']
            win = details['win']
            loss = details['loss']
            reply += f"""

{conflict_id}: {state} in {system}.
{FACTION_NAME} dominated the conflict for {score_us} days and {enemy} dominated for {score_them} days."""
            if win != '':
                reply += f'On win we get: {win}'
            if loss != '':
                reply += f'On defeat we lose: {loss}'
        await ctx.send(reply)


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
