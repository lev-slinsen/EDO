import json

import aiohttp

import settings as s


# logging.basicConfig(filename='dev.log', level=logging.INFO, format='%(created)s: %(levelname)s: %(message)s')


async def edbgs_faction(faction):
    faction_uri = faction
    for char in s.uri_chars:
        faction_uri = faction_uri.replace(char, s.uri_chars[char])
    faction_uri = f"{s.edbgs_uri}factions?name={faction_uri}"

    async with aiohttp.ClientSession() as session:
        async with session.get(faction_uri) as faction_json:
            if faction_json.status != 200:
                with open('EDO/err.log', 'a+') as err_log:
                    if s.DEBUG:
                        print(f'Bad faction status code: {faction_json.status}\n')
                    err_log.write(f'{s.frontier_time}, Bad faction status code: {faction_json.status}\n')

            faction_json_data = json.loads(await faction_json.text())
            faction_json_data['error'] = 0

            if not faction_json_data['docs']:
                print(f'{s.frontier_time}, Bad faction name: {faction}')
                with open('err.log', 'a+') as err_log:
                    err_log.write(f'{s.frontier_time}, Bad faction name: {faction}\n')
                faction_json_data['error'] = 1

            # logging.info(f'edbgs_factions for "{faction}" reply: {faction_json_data}')

            return faction_json_data


async def edbgs_system(system):
    system_uri = system
    for char in s.uri_chars:
        system_uri = system_uri.replace(char, s.uri_chars[char])
    system_uri = f"{s.edbgs_uri}systems?name={system_uri}"

    async with aiohttp.ClientSession() as session:
        async with session.get(system_uri) as system_json:
            system_json_data = json.loads(await system_json.text())

            if s.DEBUG:
                print(f'edbgs_system for "{system}" reply: {system_json_data}')

            return system_json_data['docs'][0]


async def eddb_pop_systems(state):
    state_uri = state
    for char in s.uri_chars:
        state_uri = state_uri.replace(char, s.uri_chars[char])
    state_uri = f"{s.eddb_uri}populatedsystems?statenames={state_uri}"

    async with aiohttp.ClientSession() as session:
        async with session.get(state_uri) as system_json:
            pages = json.loads(await system_json.text())['pages']
            system_json_data = json.loads(await system_json.text())
            if pages > 1:
                for page in range(2, pages+1):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{state_uri}&page={page}") as system_json:
                            system_json_data_page = json.loads(await system_json.text())
                            for system in system_json_data_page['docs']:
                                system_json_data['docs'].append(system)

                if s.DEBUG:
                    print(f'eddb_pop_systems for "{state}" reply: {system_json_data}')

                return system_json_data['docs']
