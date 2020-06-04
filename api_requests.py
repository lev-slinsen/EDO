import json
import os
from datetime import datetime

import aiohttp
import pytz
from dotenv import load_dotenv

load_dotenv()
DEBUG = os.getenv('DEBUG')

edbgs_uri = 'https://elitebgs.app/api/ebgs/v4/'
eddb_uri = 'https://eddbapi.kodeblox.com/api/v4/'

frontier_tz = pytz.timezone('UTC')
frontier_time = datetime.now(frontier_tz)


async def edbgs_faction(faction):
    faction_uri = faction.replace(' ', '%20')
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{edbgs_uri}factions?name={faction_uri}") as faction_json:
            if faction_json.status != 200:
                with open('EDO/err.log', 'a+') as err_log:
                    if DEBUG:
                        print(f'Bad faction status code: {faction_json.status}\n')
                    err_log.write(f'{frontier_time}, Bad faction status code: {faction_json.status}\n')

            faction_json_data = json.loads(await faction_json.text())
            faction_json_data['error'] = 0

            if not faction_json_data['docs']:
                print(f'{frontier_time}, Bad faction name: {faction}')
                with open('err.log', 'a+') as err_log:
                    err_log.write(f'{frontier_time}, Bad faction name: {faction}\n')
                faction_json_data['error'] = 1

            if DEBUG:
                print(f'edbgs_factions for "{faction}" reply: {faction_json_data}')

            return faction_json_data


async def edbgs_system(system):
    system_uri = system.replace(' ', '%20')
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{edbgs_uri}systems?name={system_uri}") as system_json:
            system_json_data = json.loads(await system_json.text())

            if DEBUG:
                print(f'edbgs_system for "{system}" reply: {system_json_data}')

            return system_json_data['docs'][0]


async def eddb_pop_systems(state):
    state_uri = state.replace(' ', '%20')
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{eddb_uri}populatedsystems?statenames={state_uri}") as system_json:
            pages = json.loads(await system_json.text())['pages']
            system_json_data = json.loads(await system_json.text())
            if pages > 1:
                for page in range(2, pages+1):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{eddb_uri}populatedsystems?statenames={state_uri}&page={page}") as system_json:
                            system_json_data_page = json.loads(await system_json.text())
                            for system in system_json_data_page['docs']:
                                system_json_data['docs'].append(system)

                if DEBUG:
                    print(f'eddb_pop_systems for "{state}" reply: {system_json_data}')

                return system_json_data['docs']




