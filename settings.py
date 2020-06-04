import os
from datetime import datetime

import pytz
from dotenv import load_dotenv

"Environment variables"
load_dotenv()
ADMIN_ROLE = os.getenv('ADMIN_ROLE')
CHANNEL_ADMIN = int(os.getenv('CHANNEL_ADMIN'))
DEBUG = os.getenv('DEBUG')
FACTION_NAME = os.getenv('FACTION_NAME').lower()
TOKEN = os.getenv('DISCORD_TOKEN')

"API urls"
edbgs_uri = 'https://elitebgs.app/api/ebgs/v4/'
eddb_uri = 'https://eddbapi.kodeblox.com/api/v4/'
uri_chars = {'&': '%26', ' ': '%20'}

"Time settings"
frontier_tz = pytz.timezone('UTC')
frontier_time = datetime.now(frontier_tz)

"Message texts"
number_emoji = (':zero:', ':one:', ':two:', ':three:', ':four:', ':five:',
                ':six:', ':seven:', ':eight:', ':nine:', ':keycap_ten:')
errors_text = {1: '`No such faction. Please check faction name and try again.`',
               2: '`Unable to add comment to this objective. '
                  'Instead, try changing objective text with the "!event" command.`',
               3: '`There is no event to delete.`',
               4: '`There are multiple events, please select the one to delete with respective the number.`',
               5: '`Incorrect event selected for change.`',
               6: "`There's a different number of objectives, please try again.`",
               7: '`Typo?`',
               8: '`This message will self-update every 30 minutes. '
                  'Please mention outside of this report to avoid mention spam.`'}