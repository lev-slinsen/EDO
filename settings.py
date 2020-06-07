import logging
import logging.handlers as handlers
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


class Logger:
    def __init__(self, name, file_handler, formatter, stream_handler):
        if not os.path.exists('Logs'):
            os.makedirs('Logs')
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        if stream_handler:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self.logger.addHandler(stream_handler)


logger_dev = Logger('dev',
                    handlers.TimedRotatingFileHandler(f'Logs/dev.log', when='midnight',
                                                      backupCount=2, encoding='utf-8'),
                    logging.Formatter('%(asctime)s : %(levelname)s : %(filename)s : %(funcName)s : %(message)s'),
                    True)

logger_usr = Logger('usr',
                    handlers.RotatingFileHandler(f'Logs/usr.log', maxBytes=7 * 1024 * 1024,
                                                 backupCount=2, encoding='utf-8'),
                    logging.Formatter('%(asctime)s : %(message)s'),
                    False)
