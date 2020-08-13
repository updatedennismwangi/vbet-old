import argparse
from typing import List

from vbet.core import settings
from vbet.utils.parser import create_dir


def parse_args(args: List):
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', default=settings.DEFAULT_API_NAME, choices=settings.API_BACKENDS, help=f'Select an api '
                                                                                                     f'backend to '
                                                                                 f'initialize. Default'
                                                                                 f' {settings.DEFAULT_API_NAME}')
    parser.add_argument('-p', '--port', default=settings.WS_PORT, type=int, help=f'WS server port higher than 1000 for '
                                                                                 f'api '
                                                                                 f'connection. Default {settings.WS_PORT}')
    parser.add_argument('-d', action='store_true', help=f'Set the asyncio event loop debug to true or false. Default '
                                                        f'{settings.LOOP_DEBUG}')
    parser.add_argument('-v', action='count', default=0, help=f'Set the Verbose level with highest -vv. Default -v')

    return parser.parse_args(args)


def setup(args):
    settings.API_NAME = args.a
    settings.WS_PORT = args.port
    settings.LOOP_DEBUG = args.d
    verbose = args.v

    if verbose == 0:
        settings.LOG_LEVEL = 'INFO'
        settings.FILE_LOG_LEVEL = 'INFO'
    elif verbose == 1:
        settings.LOG_LEVEL = 'INFO'
        settings.FILE_LOG_LEVEL = 'DEBUG'
    else:
        settings.LOG_LEVEL = 'DEBUG'
        settings.FILE_LOG_LEVEL = 'DEBUG'

    create_dir(settings.LOG_DIR)
    create_dir(settings.TMP_DIR)
    create_dir(settings.DATA_DIR)
    create_dir(settings.CACHE_DIR)
    for game in settings.LIVE_GAMES:
        create_dir(f'{settings.CACHE_DIR}/{game}')


def application(args: List) -> int:
    # Configure settings
    args = parse_args(args)
    setup(args)

    # Logging setup
    from vbet.utils.logger import setup_logger
    setup_logger()

    # Start up
    from vbet.core.vbet import Vbet
    app = Vbet()
    return app.run()
