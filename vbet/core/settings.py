import os
import inspect

exec_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
BASE_DIR = '/home/update/Desktop/www/app'

WS_HOST = 'localhost'
WS_PORT = 9000

BETIKA = 'betika'
MOZART = 'mozart'

API_NAME = BETIKA

DEBUG = True

REDIS_URI = 'redis://localhost:6379'

CACHE_DIR = f'{BASE_DIR}/cache'

TMP_DIR = f'{BASE_DIR}/data'

LOG_DIR = f'{BASE_DIR}/logs'

GERMANY = 41047
LALIGA = 14036
PREMIER = 14045
ITALY = 14035
KENYAN = 14050

LIVE_GAMES = [ITALY, LALIGA, PREMIER, GERMANY, KENYAN]

SERVERS = ['52.30.183.76', '52.210.189.174']


def setup():
    pass


