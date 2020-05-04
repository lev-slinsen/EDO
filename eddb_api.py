import datetime
import json
import os
from datetime import datetime
from datetime import timedelta

import pytz
import requests
from dotenv import load_dotenv

load_dotenv()
DEBUG = os.getenv('DEBUG')

req_uri = 'https://elitebgs.app/api/ebgs/v4/'
frontier_tz = pytz.timezone('UTC')
frontier_time = datetime.now(frontier_tz)


class Cache:
    def faction_update(self):
        self.FACTION_NAME = os.getenv('FACTION_NAME').lower()
        req_faction = self.FACTION_NAME.replace(' ', '%20')
        faction_json = requests.get(f"{req_uri}factions?name={req_faction}")

        if faction_json.status_code != 200:
            with open('EDO/err.log', 'a+') as err_log:
                if DEBUG:
                    print(f'Bad faction status code: {faction_json.status_code}')
                err_log.write(f'{datetime.datetime.now()}, Bad faction status code: {faction_json.status_code}\n')

        faction_json_data = json.loads(faction_json.text)
        faction_json_data['error'] = 0

        if DEBUG:
            print(f'Cached faction: {faction_json_data}')

        if not faction_json_data['docs']:
            with open('err.log', 'a+') as err_log:
                print(f'{frontier_time}, Bad faction name: {req_faction}')
                err_log.write(f'{frontier_time}, Bad faction name: {req_faction}\n')
            faction_json_data['error'] = 1

        return faction_json_data

    def stake_text(self, station):
        text = ''
        if (
                station and
                station not in self.stations
        ):
            station_name = station.replace(' ', '%20')
            station_json = requests.get(f"{req_uri}stations?name={station_name}")
            station_json_data = json.loads(station_json.text)
            if DEBUG:
                print(f'  > Station data: {station_json_data}')
            if station_json_data['total'] == 0:
                self.stations[station] = 'Installation'
            else:
                if station_json_data['docs'][0]['type'] in ('coriolis', 'coriolis starport'):
                    self.stations[station] = f'Coriolis starport, L'
                elif station_json_data['docs'][0]['type'] in ('bernal', 'ocellus starport'):
                    self.stations[station] = f'Ocellus starport, L'
                elif station_json_data['docs'][0]['type'] in ('orbis', 'orbis starport'):
                    self.stations[station] = f'Orbis starport, L'
                elif station_json_data['docs'][0]['type'] in ('crateroutpost', 'surfacestation',
                                                              'planetary outpost', 'planetary port', 'craterport'):
                    self.stations[station] = f'Surface station, L'
                elif station_json_data['docs'][0]['type'] == 'asteroidbase':
                    self.stations[station] = f'Asteroid base, L'
                elif station_json_data['docs'][0]['type'] == 'megaship':
                    self.stations[station] = f'Megaship, L'
                elif station_json_data['docs'][0]['type'][-7:] == 'outpost':
                    self.stations[station] = f'Outpost, M'
                else:
                    self.stations[station] = f'**Unknown type**'

            text = f'{station} ({self.stations[station]})'
        return text

    def get_conflicts_active(self, faction_data):
        report = {}
        if not faction_data['docs']:
            return
        for system in faction_data['docs'][0]['faction_presence']:
            if system['conflicts']:
                if system['conflicts'][0]['status'] == 'active':
                    system_name_lower = system['system_name_lower'].replace(' ', '%20')
                    system_json = requests.get(f"{req_uri}systems?name={system_name_lower}")
                    system_json_data = json.loads(system_json.text)
                    if DEBUG:
                        print(f' > Conflict system data: {system_json_data}')

                    for conflict in system_json_data['docs'][0]['conflicts']:
                        if (
                                conflict['status'] == 'active' and
                                (
                                        conflict['faction1']['name_lower'] == self.FACTION_NAME or
                                        conflict['faction2']['name_lower'] == self.FACTION_NAME
                                )
                        ):
                            if conflict['faction1']['name_lower'] == self.FACTION_NAME:
                                us = 'faction1'
                                them = 'faction2'
                            else:
                                us = 'faction2'
                                them = 'faction1'

                            report[system['system_name']] = {
                                'state': system['conflicts'][0]['type'],
                                'opponent': conflict[them]['name'],
                                'score_us': conflict[us]['days_won'],
                                'score_them': conflict[them]['days_won'],
                                'win': self.stake_text(conflict[them]['stake']),
                                'loss': self.stake_text(conflict[us]['stake']),
                                'updated_at': system['updated_at']
                            }
        if DEBUG:
            print('Cached conflicts_active:', report)
        return report

    def get_conflicts_pending(self, faction_data):
        report = {}
        for system in faction_data['docs'][0]['faction_presence']:
            if system['conflicts']:
                if system['conflicts'][0]['status'] == 'pending':
                    opponent_name = system['conflicts'][0]['opponent_name']
                    opp_faction_json = requests.get(f"{req_uri}factions?name={opponent_name}")
                    opp_faction_json_data = json.loads(opp_faction_json.text)

                    for opp_system in opp_faction_json_data['docs'][0]['faction_presence']:
                        if opp_system['conflicts']:
                            if opp_system['conflicts'][0]['opponent_name_lower'] == self.FACTION_NAME:
                                report[system['system_name']] = {
                                    'state': system['conflicts'][0]['type'],
                                    'win': self.stake_text(opp_system['conflicts'][0]['stake']),
                                    'loss': self.stake_text(system['conflicts'][0]['stake']),
                                    'updated_at': system['updated_at']
                                }
        if DEBUG:
            print('Cached conflicts_pending:', report)
        return report

    def get_conflicts_recovering(self, faction_data):
        report = {}
        for system in faction_data['docs'][0]['faction_presence']:
            if system['conflicts']:
                if (
                        system['conflicts'][0]['status'] == 'recovering' or
                        system['conflicts'][0]['status'] == ''
                ):
                    opponent_name = system['conflicts'][0]['opponent_name']
                    opp_faction_json = requests.get(f"{req_uri}factions?name={opponent_name}")
                    opp_faction_json_data = json.loads(opp_faction_json.text)

                    for opp_system in opp_faction_json_data['docs'][0]['faction_presence']:
                        if opp_system['conflicts']:
                            if opp_system['conflicts'][0]['opponent_name_lower'] == self.FACTION_NAME:
                                days_won = system['conflicts'][0]['days_won']
                                opp_days_won = opp_system['conflicts'][0]['days_won']
                                if days_won > opp_days_won:
                                    status = 'victory'
                                    stake = system['conflicts'][0]['stake']
                                else:
                                    status = 'defeat'
                                    stake = opp_system['conflicts'][0]['stake']

                                report[system['system_name']] = {
                                    'state': system['conflicts'][0]['type'],
                                    'status': status,
                                    'days_won': days_won,
                                    'days_lost': opp_days_won,
                                    'stake': self.stake_text(stake),
                                    'updated_at': system['updated_at']
                                }
        if DEBUG:
            print('Cached conflicts_recovering:', report)
        return report

    def get_unvisited_systems(self, faction_data):
        report = {2: [], 3: [], 4: [], 5: [], 6: [], 7: []}
        for system in faction_data['docs'][0]['faction_presence']:
            if (
                    system['system_name'] not in self.conflicts_active and
                    system['system_name'] not in self.conflicts_pending
            ):
                updated_ago = (frontier_time -
                               frontier_tz.localize(datetime.strptime(system['updated_at'][0:16], '%Y-%m-%dT%H:%M')))
                for day in report:
                    if timedelta(days=day+1) > updated_ago > timedelta(days=day) and updated_ago < timedelta(days=7):
                        report[day].append(system['system_name'])
                if updated_ago >= timedelta(days=7):
                    report[7].append(system['system_name'])
        if DEBUG:
            print('Cached unvisited_systems:', report, '\n')
        return report

    def __init__(self):
        self.stations = {}
        self.faction_data = self.faction_update()
        if self.faction_data['error'] != 0:
            return
        self.conflicts_active = self.get_conflicts_active(self.faction_data)
        self.conflicts_recovering = self.get_conflicts_recovering(self.faction_data)
        self.conflicts_pending = self.get_conflicts_pending(self.faction_data)
        self.unvisited_systems = self.get_unvisited_systems(self.faction_data)

    def __call__(self):
        return (self.conflicts_active,
                self.conflicts_recovering,
                self.conflicts_pending)
