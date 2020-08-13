import asyncio
import signal
from typing import Optional

import vbet
from vbet.core import settings
from vbet.core.user_manager import UserManager
from vbet.core.ws_server import WsServer
from vbet.utils import exceptions
from vbet.utils.log import get_logger

logger = get_logger('vbet')

STARTING = 0
CLOSING = 1
LIVE = 100

EXIT_SUCCESS = 100
EXIT_INTERRUPT = 101


def setup_signal_handlers():
    signal.signal(signal.SIGTERM, sig_term)


def sig_term(sig: int, frame):
    logger.info('SIG_TERM terminating server')
    raise KeyboardInterrupt


class Vbet:
    status: int = STARTING  # Show server status.
    exit_flag: bool = False  # Set to True if exit is from shell and False if Ctrl + C.
    loop: Optional[asyncio.AbstractEventLoop] = None  # default event loop.
    close_event: asyncio.Event = asyncio.Event()  # Set when the ws server and the user manager are done.
    exit_code: int = 0

    def __init__(self):
        self.ws_server: WsServer = WsServer(self)  # Ws server service endpoint.

        self.manager: UserManager = UserManager(self)  # User manager player handler.

    def run(self) -> int:
        logger.info(f'Vbet Server build {vbet.__VERSION__}')
        self.setup_event_loop()  # Get and Setup event loop
        setup_signal_handlers()  # Install custom signal handlers

        # Setup ws server and the user manager loop
        manager_future = self.loop.create_task(self.manager.setup())  # Setup user manager
        ws_future = self.loop.create_task(self.ws_server.setup())  # Setup websocket server
        future = self.loop.create_task(asyncio.wait([manager_future, ws_future], return_when=asyncio.ALL_COMPLETED))
        future.add_done_callback(lambda x: self.loop.stop())
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        else:
            try:
                logger.info(f'Server online. API_NAME[{settings.API_NAME}] . Press Ctrl + C to terminate')
                self.status = LIVE
                while not self.exit_flag:
                    self.loop.run_forever()
                raise KeyboardInterrupt
            except KeyboardInterrupt:
                try:
                    # Graceful shutdown
                    self.status = CLOSING
                    logger.info('Gracefully terminating server')

                    self.teardown()
                except KeyboardInterrupt:
                    self.exit_code = EXIT_INTERRUPT
                    self.cancel_tasks()
                    logger.info(f'Cold shutdown')
                else:
                    self.exit_code = EXIT_SUCCESS
        finally:
            self.loop.close()
            logger.info(f'Terminated application: {self.exit_code}')
            return self.exit_code

    def setup_event_loop(self):
        # Set current loop
        self.loop = asyncio.get_event_loop()

        # Custom event loop error handler
        self.loop.set_exception_handler(self.exception_handler)
        self.loop.set_debug(settings.LOOP_DEBUG)

    def teardown(self):
        server_task = self.loop.create_task(self.ws_server.wait_closed())
        manager_task = self.loop.create_task(self.manager.wait_closed())
        tasks = asyncio.gather(*[server_task, manager_task], return_exceptions=True)
        tasks.add_done_callback(self.teardown_callback)

        # Run event loop until all tasks are completed
        while not self.loop.is_running() and not self.close_event.is_set():
            self.loop.run_forever()

    def teardown_callback(self, future: asyncio.Future):
        self.close_event.set()
        raise exceptions.StopApplication

    def cancel_tasks(self):
        # Cancel all pending tasks
        tasks = asyncio.gather(*asyncio.Task.all_tasks(), return_exceptions=True)
        tasks.add_done_callback(lambda a: self.loop.stop())

    def exception_handler(self, loop, context):
        if 'exception' in context:
            if isinstance(context['exception'], exceptions.StopApplication):
                logger.info(f'Server shutdown success')
                self.loop.stop()
            elif isinstance(context['exception'], asyncio.CancelledError):
                print(context)
            elif 'exception' not in context or not isinstance(context['exception'], asyncio.CancelledError):
                loop.default_exception_handler(context)

    # API calls
    async def exit_uri(self, session_key: int, body):
        if not self.exit_flag and self.status != CLOSING:
            self.exit_flag = True
            self.loop.stop()
