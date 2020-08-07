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

GERMANY = 41047
LALIGA = 14036
PREMIER = 14045
ITALY = 14035
KENYAN = 14050

LIVE_GAMES = [ITALY, LALIGA, PREMIER, GERMANY, KENYAN]

SERVERS = ['52.30.183.76', '52.210.189.174']


def setup():
    from vbet.utils.iofile import create_dir
    create_dir(LOG_DIR)
    create_dir(TMP_DIR)
    create_dir(DATA_DIR)
    create_dir(CACHE_DIR)
    for game in LIVE_GAMES:
        create_dir(f'{CACHE_DIR}/{game}')

