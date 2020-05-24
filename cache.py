import datetime
import json
import os
from datetime import datetime
from datetime import timedelta
import numpy as np

#import aiohttp
import pytz
from dotenv import load_dotenv

import api_requests
from log import logEvent

load_dotenv()
DEBUG = os.getenv('DEBUG')
LOG = os.getenv('LOG')
FACTION_NAME = os.getenv('FACTION_NAME').lower()

edbgs_uri = 'https://elitebgs.app/api/ebgs/v4/'
eddb_uri = 'https://eddbapi.kodeblox.com/api/v4/'
frontier_tz = pytz.timezone('UTC')
frontier_time = datetime.now(frontier_tz)


def distanceFrom(inList1, inList2) : #inList in format of [x,y,z] all as int
    p1 = np.array(inList1)
    p2 = np.array(inList2)
    squared_dist = np.sum((p1-p2)**2, axis=0)
    dist = np.sqrt(squared_dist)
    return(dist)

def updated_ago_text(updated_at_data):
    updated_at = frontier_tz.localize(datetime.strptime(updated_at_data[0:16], '%Y-%m-%dT%H:%M'))
    highlight = False
    updated_ago = (frontier_time - updated_at)

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


class Cache:
    def __init__(self):
        self.stations = {}

    async def gather_data(self):
        self.faction_data = await api_requests.edbgs_faction(FACTION_NAME)
        if self.faction_data['error'] != 0:
            return
        self.retreating_systems = await self.get_retreating_systems(self.faction_data)
        self.conflicts_active = await self.get_conflicts_active(self.faction_data)
        self.conflicts_pending = await self.get_conflicts_pending(self.faction_data)
        self.conflicts_recovering = await self.get_conflicts_recovering(self.faction_data)
        self.unvisited_systems = await self.get_unvisited_systems(self.faction_data)
        # self.ltd_systems = await self.get_ltd_systems()

        if DEBUG: print('Cache init done')
        if LOG: await logEvent("Cache init done","")

    # async def stake_text(self, station):
    #     text = ''
    #     if (
    #             station and
    #             station not in self.stations
    #     ):
    #         station_name = station.replace(' ', '%20')
    #         async with aiohttp.ClientSession() as session:                                                     #if this gets uncommented at some point please rewrite this to use api_requests.py instead
    #             async with session.get(f"{edbgs_uri}stations?name={station_name}") as station_json:
    #                 station_json_data = json.loads(await station_json.text())
    #                 if DEBUG:
    #                     print(f'  > Station data: {station_json_data}')
    #                 #if this is reintegrated, add logEvent() here
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

    async def get_retreating_systems(self, faction_data) :
        report = {}
        for system in faction_data['docs'][0]['faction_presence']:
            if system['state']=="retreat" : #not sure what the exact word is for retrea, just taking a guess on this
                report[system['system_name']] = {
                    'updated_ago': await updated_ago_text(system['updated_at']),
                    'status':'active',
                    'influence': system["influence"]
                }
            for pendingState in system["pending_states"] :
                if pendingState["state"]=="retreat" : #same as above
                    report[system['system_name']] = {
                        'updated_ago': await updated_ago_text(system['updated_at']),
                        'status':'pending',
                        'influence':system["influence"]
                    }
            for recoveringState in system["recovering_states"] :
                if recoveringState["state"]=="retreat" : #same as above
                    report[system['system_name']] = {
                        'updated_ago': await updated_ago_text(system['updated_at']),
                        'status':'recovering',
                        'influence':system["influence"]
                    }
        if DEBUG : print('Cached retreating_systems ', report)
        if LOG: await logEvent("Cached retreating_systems","") #excluding details for now for simplicity, maybe add later?
        return report

    async def get_conflicts_active(self, faction_data):
        report = {}
        if not faction_data['docs']:
            return
        for system in faction_data['docs'][0]['faction_presence']:
            if system['conflicts']:
                if system['conflicts'][0]['status'] == 'active':
                    system_name_lower = system['system_name_lower']
                    data = await api_requests.edbgs_system(system_name_lower)

                    for conflict in data['conflicts']:
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

                            report[system['system_name']] = {
                                'state': system['conflicts'][0]['type'],
                                'opponent': conflict[them]['name'],
                                'score_us': conflict[us]['days_won'],
                                'score_them': conflict[them]['days_won'],
                                'win': conflict[them]['stake'],
                                'loss': conflict[us]['stake'],
                                'updated_ago': updated_ago_text(system['updated_at'])
                            }
        if DEBUG: print('Cached conflicts_active:', report)
        if LOG: await logEvent("Cached conflicts_active","")
        return report

    async def get_conflicts_pending(self, faction_data):
        report = {}
        for system in faction_data['docs'][0]['faction_presence']:
            if system['conflicts']:
                if system['conflicts'][0]['status'] == 'pending':
                    opponent_name = system['conflicts'][0]['opponent_name']
                    opp_faction_data = await api_requests.edbgs_faction(opponent_name)

                    for opp_system in opp_faction_data['docs'][0]['faction_presence']:
                        if opp_system['conflicts']:
                            if opp_system['conflicts'][0]['opponent_name_lower'] == FACTION_NAME:
                                report[system['system_name']] = {
                                    'state': system['conflicts'][0]['type'],
                                    'opponent': system['conflicts'][0]['opponent_name'],
                                    'win': opp_system['conflicts'][0]['stake'],
                                    'loss': system['conflicts'][0]['stake'],
                                    'updated_ago': updated_ago_text(system['updated_at'])
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
                    opp_faction_json_data = await api_requests.edbgs_faction(opponent_name)
                    for opp_system in opp_faction_json_data['docs'][0]['faction_presence']:
                        if opp_system['conflicts']:
                            if opp_system['conflicts'][0]['opponent_name_lower'] == FACTION_NAME:
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
                                    'updated_ago': updated_ago_text(system['updated_at'])
                                }
        if DEBUG: print('Cached conflicts_recovering:', report)
        if LOG: await logEvent("Cached conflicts_recovering","")
        return report

    async def get_unvisited_systems(self, faction_data):
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
        if DEBUG: print('Cached unvisited_systems:', report)
        if LOG: await logEvent("Cached unvisited_systems","")
        return report

    async def get_ltd_systems(self):
        systems_list = {}
        ph_system_json_data, pages = await api_requests.eddb_publicHolidaySystems_all() #ping api
        for system in ph_system_json_data['docs']:
            if len(system["states"]) >= 4 : #rule out a buncha systems
                for state in system['states']:
                    if state['name_lower'] == 'expansion':
                        for state in system['states']:
                            if state['name_lower'] == 'civil liberty':
                                for state in system['states']:
                                    if state['name_lower'] == 'investment' or state['name_lower'] == 'boom':
                                        system_name_lower = system['name_lower']
                                        system_json_data = await api_requests.eddb_system(system_name_lower)
                                        systems_list[system_json_data['name']] = []
                                        stations_json_data = await api_requests.eddb_station(system_json_data)
                                        for station in stations_json_data:
                                            if station['controlling_minor_faction'] == system['controlling_minor_faction']:
                                                systems_list[system_json_data['name']].append(
                                                    {
                                                        'name': station['name'],
                                                        'distance': int(station['distance_from_star']),
                                                        'distFromBoran': distanceFrom([system["x"], system["y"], system["z"]], [123.03125, -0.25, 2.84375]),
                                                        'type': station['type']
                                                    }
                                                )
        if pages > 1:
            for page, x in enumerate(range(1, pages)):
                page += 1
                ph_system_json_data = await api_requests.eddb_publicHolidaySystems_page(page) 
                for system in ph_system_json_data['docs']:
                    if len(system["states"]) >= 4 : #rule out a buncha systems
                        for state in system['states']:
                            if state['name_lower'] == 'expansion':
                                for state in system['states']:
                                    if state['name_lower'] == 'civil liberty':
                                        for state in system['states']:
                                            if state['name_lower'] == 'investment' or state['name_lower'] == 'boom':
                                                system_name_lower = system['name_lower']
                                                system_json_data = await api_requests.eddb_system(system_name_lower)
                                                systems_list[system_json_data['name']] = []
                                                stations_json_data = await api_requests.eddb_station(system_json_data)
                                                for station in stations_json_data:
                                                    if station['controlling_minor_faction'] == system['controlling_minor_faction']:
                                                        systems_list[system_json_data['name']].append(
                                                            {
                                                                'name': station['name'],
                                                                'distance': int(station['distance_from_star']),
                                                                'distFromBoran': distanceFrom([system["x"], system["y"], system["z"]], [123.03125, -0.25, 2.84375]),
                                                                'type': station['type']
                                                            }
                                                        )
        if DEBUG: print(f'Cached ltd_systems: {systems_list}')
        if LOG: await logEvent("Cached ltd_systems",f"{systems_list}")
        return systems_list
