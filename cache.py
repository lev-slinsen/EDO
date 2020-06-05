import datetime
from datetime import datetime
from datetime import timedelta

import numpy as np

import requests
import settings as s


class Cache:
    def __init__(self):
        self.stations = {}

    async def gather_data(self):
        self.faction_data = await self.faction_update()
        if self.faction_data['error'] != 0:
            return
        self.conflicts_active = await self.get_conflicts_active(self.faction_data)
        self.conflicts_pending = await self.get_conflicts_pending(self.faction_data)
        self.conflicts_recovering = await self.get_conflicts_recovering(self.faction_data)
        self.unvisited_systems = await self.get_unvisited_systems(self.faction_data)
        self.ltd_systems = await self.get_ltd_systems()

        if s.DEBUG:
            print('Cache init done')

    async def faction_update(self):
        data = await requests.edbgs_faction(s.FACTION_NAME)
        home_system_name = data['docs'][0]['faction_presence'][0]['system_name']
        self.home_system = await requests.edbgs_system(home_system_name)
        return data

    async def updated_ago_text(self, updated_at_data):
        updated_at = s.frontier_tz.localize(datetime.strptime(updated_at_data[0:16], '%Y-%m-%dT%H:%M'))
        highlight = False
        updated_ago = (s.frontier_time - updated_at)

        if updated_ago < timedelta(seconds=0):  # Prevents random bug that subtracts 2 days from timedelta
            print('!ALERT')
            updated_ago += timedelta(days=1)
            updated_ago = timedelta(days=1) - updated_ago
        if updated_ago < timedelta(seconds=0):
            updated_ago = timedelta(days=1)
        if updated_ago >= timedelta(hours=12):
            highlight = True

        updated_ago_text = str(updated_ago).split(':')[0]
        if (
                updated_ago_text[-2:] == '1' or
                updated_ago_text[-2:] == ' 1' or
                updated_ago_text[-2:] == '21'
        ):
            text = f'{updated_ago_text} hour ago'
        elif updated_ago_text[-2:] == '0':
            text = 'less than an hour ago'
        else:
            text = f'{updated_ago_text} hours ago'

        if highlight:
            text = f'**{text}**'
        return text

    # async def stake_text(self, station):
    #     text = ''
    #     if (
    #             station and
    #             station not in self.stations
    #     ):
    #         station_name = station.replace(' ', '%20')
    #         async with aiohttp.ClientSession() as session:
    #             async with session.get(f"{edbgs_uri}stations?name={station_name}") as station_json:
    #                 station_json_data = json.loads(await station_json.text())
    #                 if DEBUG:
    #                     print(f'  > Station data: {station_json_data}')
    #                 if station_json_data['total'] == 0:
    #                     self.stations[station] = 'Settlement'
    #                 else:
    #                     if station_json_data['docs'][0]['type'] in ('coriolis', 'coriolis starport'):
    #                         self.stations[station] = f'Coriolis starport, L'
    #                     elif station_json_data['docs'][0]['type'] in ('bernal', 'ocellus starport'):
    #                         self.stations[station] = f'Ocellus starport, L'
    #                     elif station_json_data['docs'][0]['type'] in ('orbis', 'orbis starport'):
    #                         self.stations[station] = f'Orbis starport, L'
    #                     elif station_json_data['docs'][0]['type'] in ('crateroutpost', 'planetary port', 'craterport'):
    #                         self.stations[station] = f'Surface station, L'
    #                     elif station_json_data['docs'][0]['type'] == 'asteroidbase':
    #                         self.stations[station] = f'Asteroid base, L'
    #                     elif station_json_data['docs'][0]['type'] == 'megaship':
    #                         self.stations[station] = f'Megaship, L'
    #                     elif station_json_data['docs'][0]['type'] in ('planetary outpost', 'surfacestation'):
    #                         self.stations[station] = f'Settlement'
    #                     elif station_json_data['docs'][0]['type'][-7:] == 'outpost':
    #                         self.stations[station] = f'Outpost, M'
    #                     else:
    #                         self.stations[station] = f'**Unknown type**'
        #     text = f'{station} ({self.stations[station]})'
        # return text

    async def get_conflicts_active(self, faction_data):
        report = {}
        if not faction_data['docs']:
            return
        for system in faction_data['docs'][0]['faction_presence']:
            if system['conflicts']:
                if system['conflicts'][0]['status'] == 'active':
                    system_name_lower = system['system_name_lower']
                    data = await requests.edbgs_system(system_name_lower)

                    for conflict in data['conflicts']:
                        if (
                                conflict['status'] == 'active' and
                                (
                                        conflict['faction1']['name_lower'] == s.FACTION_NAME or
                                        conflict['faction2']['name_lower'] == s.FACTION_NAME
                                )
                        ):
                            if conflict['faction1']['name_lower'] == s.FACTION_NAME:
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
                                'win': conflict[them]['stake'],
                                'loss': conflict[us]['stake'],
                                'updated_ago': await self.updated_ago_text(system['updated_at'])
                            }
        if s.DEBUG:
            print('Cached conflicts_active:', report)
        return report

    async def get_conflicts_pending(self, faction_data):
        report = {}
        for system in faction_data['docs'][0]['faction_presence']:
            if system['conflicts']:
                if system['conflicts'][0]['status'] == 'pending':
                    opponent_name = system['conflicts'][0]['opponent_name']
                    opp_faction_data = await requests.edbgs_faction(opponent_name)

                    for opp_system in opp_faction_data['docs'][0]['faction_presence']:
                        if opp_system['conflicts']:
                            if opp_system['conflicts'][0]['opponent_name_lower'] == s.FACTION_NAME:
                                report[system['system_name']] = {
                                    'state': system['conflicts'][0]['type'],
                                    'opponent': system['conflicts'][0]['opponent_name'],
                                    'win': opp_system['conflicts'][0]['stake'],
                                    'loss': system['conflicts'][0]['stake'],
                                    'updated_ago': await self.updated_ago_text(system['updated_at'])
                                }
        return report

    async def get_conflicts_recovering(self, faction_data):
        report = {}
        for system in faction_data['docs'][0]['faction_presence']:
            if system['conflicts']:
                if (
                        system['conflicts'][0]['status'] == 'recovering' or
                        system['conflicts'][0]['status'] == ''
                ):
                    opponent_name = system['conflicts'][0]['opponent_name']
                    opp_faction_data = await requests.edbgs_faction(opponent_name)

                    for opp_system in opp_faction_data['docs'][0]['faction_presence']:
                        if opp_system['conflicts']:
                            if opp_system['conflicts'][0]['opponent_name_lower'] == s.FACTION_NAME:
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
                                    'stake': stake,
                                    'updated_ago': await self.updated_ago_text(system['updated_at'])
                                }
        if s.DEBUG:
            print('Cached conflicts_recovering:', report)
        return report

    async def get_unvisited_systems(self, faction_data):
        report = {2: [], 3: [], 4: [], 5: [], 6: [], 7: []}
        for system in faction_data['docs'][0]['faction_presence']:
            if (
                    system['system_name'] not in self.conflicts_active and
                    system['system_name'] not in self.conflicts_pending
            ):
                updated_ago = (s.frontier_time -
                               s.frontier_tz.localize(datetime.strptime(system['updated_at'][0:16], '%Y-%m-%dT%H:%M')))

                for day in report:
                    if timedelta(days=day+1) > updated_ago > timedelta(days=day) and updated_ago < timedelta(days=7):
                        report[day].append(system['system_name'])
                if updated_ago >= timedelta(days=7):
                    report[7].append(system['system_name'])
        if s.DEBUG:
            print('Cached unvisited_systems:', report)
        return report

    async def get_ltd_systems(self):
        systems_list = {}
        systems_data = await requests.eddb_pop_systems('public holiday')

        for system in systems_data:
            check = []
            for state in system['states']:
                if state['name_lower'] == 'expansion':
                    check.append(1)
                elif state['name_lower'] == 'civil liberty':
                    check.append(1)
                elif state['name_lower'] == 'investment' or state['name_lower'] == 'boom':
                    check.append(1)
                else:
                    break

                if len(check) == 3:
                    systems_list[system['name']] = {}

                    home_coordinates = np.array([self.home_system['x'], self.home_system['y'], self.home_system['z']])
                    target_coordinates = np.array([system['x'], system['y'], system['z']])
                    squared_dist = np.sum((home_coordinates - target_coordinates) ** 2, axis=0)
                    distance = np.sqrt(squared_dist)
                    systems_list[system['name']]['distance'] = str(np.round(distance, 1))

                    updated_ago = await self.updated_ago_text(system['updated_at'])
                    systems_list[system['name']]['updated_ago'] = updated_ago.replace('*', '')

        if s.DEBUG:
            print('Cached get_ltd_systems:', systems_list)
        return systems_list
