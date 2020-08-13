import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

WS_HOST = 'localhost'
WS_PORT = 9000

BETIKA = 'betika'
MOZART = 'mozart'

API_BACKENDS = [
	BETIKA, MOZART
]
DEFAULT_API_NAME = BETIKA
API_NAME = DEFAULT_API_NAME

DEBUG = True

LOOP_DEBUG = False

LOG_LEVEL = 'DEBUG'

FILE_LOG_LEVEL = 'DEBUG'

REDIS_URI = 'redis://localhost:6379'

TMP_DIR = f'{BASE_DIR}/tmp'

DATA_DIR = f'{TMP_DIR}/data'

CACHE_DIR = f'{TMP_DIR}/cache'

LOG_DIR = f'{BASE_DIR}/logs'

BUNDESLIGA = 41047
LALIGA = 14036
PREMIER = 14045
CALCIO = 14035
KPL = 14050

LIVE_GAMES = [CALCIO, LALIGA, PREMIER, BUNDESLIGA, KPL]
