import json

import aiohttp

import settings as s

log = s.logger_dev.logger


async def edbgs_faction(faction):
    faction_uri = faction
    for char in s.uri_chars:
        faction_uri = faction_uri.replace(char, s.uri_chars[char])
    faction_uri = f"{s.edbgs_uri}factions?name={faction_uri}"

    async with aiohttp.ClientSession() as session:
        async with session.get(faction_uri) as faction_json:
            if faction_json.status != 200:
                log.error(f'input "{faction}", status {faction_json.status}')

            faction_json_data = json.loads(await faction_json.text())

            faction_json_data['error'] = 0
            if not faction_json_data['docs']:
                faction_json_data['error'] = 1

            log.debug(f'input "{faction}", reply {faction_json_data}')
            return faction_json_data


async def edbgs_station(station):
    station_uri = station
    for char in s.uri_chars:
        station_uri = station_uri.replace(char, s.uri_chars[char])
    station_uri = f"{s.edbgs_uri}stations?name={station_uri}"

    async with aiohttp.ClientSession() as session:
        async with session.get(station_uri) as station_json:
            if station_json.status != 200:
                log.error(f'input "{station}", status {station_json.status}')

            station_json_data = json.loads(await station_json.text())
            log.debug(f'input "{station}", reply {station_json_data}')

            return station_json_data


async def edbgs_system(system):
    system_uri = system
    for char in s.uri_chars:
        system_uri = system_uri.replace(char, s.uri_chars[char])
    system_uri = f"{s.edbgs_uri}systems?name={system_uri}"

    async with aiohttp.ClientSession() as session:
        async with session.get(system_uri) as system_json:
            if system_json.status != 200:
                log.error(f'input "{system}", status {system_json.status}')

            system_json_data = json.loads(await system_json.text())
            log.debug(f'input "{system}", reply {system_json_data}')

            return system_json_data['docs'][0]


async def eddb_pop_systems(state):
    state_uri = state
    for char in s.uri_chars:
        state_uri = state_uri.replace(char, s.uri_chars[char])
    state_uri = f"{s.eddb_uri}populatedsystems?statenames={state_uri}"

    async with aiohttp.ClientSession() as session:
        async with session.get(state_uri) as system_json:
            if system_json.status != 200:
                log.error(f'input "{state}", status {system_json.status}')

            system_json_data = json.loads(await system_json.text())
            log.debug(f'input "{state}", page 1 reply {system_json_data}')

            pages = json.loads(await system_json.text())['pages']
            if pages > 1:
                for page in range(2, pages+1):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{state_uri}&page={page}") as system_json:
                            if system_json.status != 200:
                                log.error(f'input "{state}", page {page} status {system_json.status}')

                            system_json_data_page = json.loads(await system_json.text())
                            log.debug(f'input "{state}", page {page} reply {system_json_data_page}')

                            for system in system_json_data_page['docs']:
                                system_json_data['docs'].append(system)

                log.debug(f'input "{state}", all pages combined {system_json_data}')
                return system_json_data['docs']
