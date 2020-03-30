import os
import requests
import json
import asyncio
import time
import math
import datetime

from dotenv import load_dotenv

load_dotenv()
FACTION_ID = os.getenv('FACTION_ID')
FACTION_NAME = os.getenv('FACTION_NAME').lower()
DEBUG = os.getenv('DEBUG')

req_faction = FACTION_NAME.replace(' ', '%20')
req_uri = 'https://elitebgs.app/api/ebgs/v4/'
report = ''


def faction_update():
    faction_json = requests.get(f"{req_uri}factions?name={req_faction}")
    return faction_json


faction_json_stash = faction_update()
faction_json_data = json.loads(faction_json_stash.text)


def conflicts_active():
    if DEBUG:
        print(f'"Faction" reply: {faction_json_data}')

    if not faction_json_data['docs']:
        with open('err.log', 'a+') as err_log:
            print(f'{datetime.datetime.now()}, Bad faction name: {req_faction}')
            err_log.write(f'{datetime.datetime.now()}, Bad faction name: {req_faction}')

    conflicts_active_report = {}
    n = 1
    for system in faction_json_data['docs'][0]['faction_presence']:
        if DEBUG:
            print(f'System {n}: {system["system_name"]}')
            n += 1

        for active_state in system['active_states']:

            if (
                    active_state['state'] == 'war' or
                    active_state['state'] == 'civil war' or
                    active_state['state'] == 'election'
            ):
                system_name_lower = system['system_name_lower'].replace(' ', '%20')
                system_json = requests.get(f"{req_uri}systems?name={system_name_lower}")
                system_json_data = json.loads(system_json.text)

                if DEBUG:
                    print(f'"System" reply: {system_json_data}')

                for conflict in system_json_data['docs'][0]['conflicts']:
                    if (
                            conflict['status'] == 'active' and
                            (
                                    conflict['faction1']['name_lower'] == FACTION_NAME or
                                    conflict['faction2']['name_lower'] == FACTION_NAME
                            )
                    ):
                        conflicts_active_report.update(
                            {
                                system['system_name_lower']: {
                                    'state': active_state['state'],
                                    conflict['faction1']['name_lower']: conflict['faction1']['days_won'],
                                    conflict['faction2']['name_lower']: conflict['faction2']['days_won']
                                }
                            }
                        )
    return conflicts_active_report





    # return report
