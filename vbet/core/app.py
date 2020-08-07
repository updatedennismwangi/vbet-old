from vbet.utils.log import *
from vbet.utils import exceptions
from vbet.core import settings
import vbet
import asyncio
import signal
from vbet.core.ws_server import WsServer
from vbet.core.user_manager import UserManager


logger = get_logger('vbet')


class Vbet:
    def __init__(self):
        self.close_event = asyncio.Event()

        self._exit_flag = False

        self.quit_event = asyncio.Event()

        self.loop: asyncio.BaseEventLoop = None

        self.ws_server = WsServer(self)

        self.manager = UserManager(self)

    @property
    def closing(self):
        return self.quit_event.is_set()

    def run(self):
        logger.info(f'Vbet Server version {vbet.__VERSION__}')
        self.loop = asyncio.get_event_loop()
        signal.signal(signal.SIGINT, self.sig_int)
        signal.signal(signal.SIGTERM, self.sig_term)
        self.loop.set_exception_handler(self.exception_handler)
        self.loop.set_debug(settings.LOOP_DEBUG)
        self.loop.run_until_complete(self.manager.init(self.loop))
        self.ws_server.setup()
        try:
            while not self._exit_flag:
                self.loop.run_forever()
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            try:
                # Graceful shutdown
                self.quit_event.set()
                logger.info('Gracefully terminating server')
                self.clean_up()
            except KeyboardInterrupt:
                logger.info(f'Cold shutdown')
        finally:
            self.loop.close()
            logger.info(f'Terminated application')

    async def exit_uri(self, session_key: int, body):
        if not self._exit_flag and not self.closing:
            self._exit_flag = True
            self.loop.stop()

    def clean_up(self):
        server_task = self.loop.create_task(self.ws_server.wait_closed())
        manager_task = self.loop.create_task(self.manager.wait_closed())
        tasks = asyncio.gather(*[server_task, manager_task], return_exceptions=True)
        tasks.add_done_callback(self.clean_up_callback)

        # Run event loop until all tasks are completed
        while not self.loop.is_running() and not self.close_event.is_set():
            self.loop.run_forever()

    def clean_up_callback(self, future: asyncio.Future):
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

    @staticmethod
    def sig_int(sig: int, frame):
        raise KeyboardInterrupt

    @staticmethod
    def sig_term(sig: int, frame):
        print(sig)
