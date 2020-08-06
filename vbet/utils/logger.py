import logging.config
from vbet.core import settings


config = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s : %(name)s] %(message)s',
        },
        'error-logger': {
            'format': '%(asctime)s %(filename)s [%(lineno)d ] [%(pathname)s] %(message)s'
        }
    },
    'handlers': {
        'default': {
            'level': settings.LOG_LEVEL,
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'level': settings.FILE_LOG_LEVEL,
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': f'{settings.LOG_DIR}/vbet.log'
        },
    },
    'loggers': {
        '': {
            'handlers': ['file', 'default'],
            'level': 'DEBUG',
            'propagate': False
        },
        'aiohttp': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False
        },
        'websockets': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False
        },
        'aioredis': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False
        },
        'error-logger': {
            'handlers': ['file', 'default'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
}
logging.config.dictConfig(config)

# logging.Formatter.converter = time.gmtime
