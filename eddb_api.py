import datetime
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()       # All environment variables are stored in '.env' file
FACTION_ID = os.getenv('FACTION_ID')
FACTION_NAME = os.getenv('FACTION_NAME').lower()
DEBUG = os.getenv('DEBUG')

req_faction = FACTION_NAME.replace(' ', '%20')
req_uri = 'https://elitebgs.app/api/ebgs/v4/'


def faction_update():       # Only triggered by Cache class to update faction info
    faction_json = requests.get(f"{req_uri}factions?name={req_faction}")
    faction_json_data = json.loads(faction_json.text)

    if DEBUG:
        print(f'"Faction" reply: {faction_json_data}')

    if not faction_json_data['docs']:
        with open('err.log', 'a+') as err_log:
            print(f'{datetime.datetime.now()}, Bad faction name: {req_faction}')
            err_log.write(f'{datetime.datetime.now()}, Bad faction name: {req_faction}')

    return faction_json_data


def get_conflicts_active(faction_data):     # Only triggered by Cache class to update systems in conflict states
    report = {}
    conflict_id = 1
    for sys_id, system in enumerate(faction_data['docs'][0]['faction_presence']):
        if DEBUG:
            print(f'System {sys_id+1}: {system["system_name"]}')

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
                        if conflict['faction1']['name_lower'] == FACTION_NAME:
                            us = 'faction1'
                            them = 'faction2'
                        else:
                            us = 'faction2'
                            them = 'faction1'
                        report[conflict_id] = {
                                    'system': system['system_name'],
                                    'state': active_state['state'],
                                    'enemy': conflict[them]['name'],
                                    'score_us': conflict[us]["days_won"],
                                    'score_them': conflict[them]["days_won"],
                                    'win': conflict[them]['stake'],
                                    'loss': conflict[us]['stake']
                        }
                        conflict_id += 1
    if DEBUG:
        print(f"Active conflicts report: {report}")
    return report


class Cache:
    def __init__(self):
        self.faction_data = faction_update()                                # Firstly gets faction data
        self.conflicts_active = get_conflicts_active(self.faction_data)     # Secondly gets active conflicts
