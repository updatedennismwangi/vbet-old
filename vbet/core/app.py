from vbet.utils.log import *
from vbet.core import settings
import vbet
import asyncio
from vbet.core.ws_server import WsServer
from vbet.core.user_manager import UserManager
import signal


logger = get_logger('vbet')


class Vbet:
    def __init__(self):
        self.close_event = asyncio.Event()

        self.quit_event = asyncio.Event()

        self.close_future: asyncio.Future = None

        self.loop: asyncio.BaseEventLoop = None

        self.ws_server = WsServer(self)

        self.manager = UserManager(self)

    @property
    def closing(self):
        return self.quit_event.is_set()

    def run(self):
        logger.info(f'Vbet Server version {vbet.__VERSION__}')
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.loop = asyncio.get_event_loop()
        self.loop.set_debug(settings.DEBUG)
        self.loop.run_until_complete(self.manager.init(self.loop))
        self.ws_server.setup()
        self.close_future = self.loop.create_task(self._terminate())
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.ws_server.shutdown()

            self.manager.shutdown()

            self.loop.run_until_complete(self.ws_server.wait_closed())

            self.loop.run_until_complete(self.manager.wait_closed())

            self.loop.run_until_complete(self.clean_up())

            self.loop.close()

        logger.info(f'Terminated application')

    async def _terminate(self):
        await self.close_event.wait()
        logger.info('Gracefully terminating server')
        raise KeyboardInterrupt()

    async def exit_uri(self, body):
        if not self.closing:
            logger.info('Ctrl + C Scheduled server shutdown')
            asyncio.create_task(self.manager.exit())
            self.quit_event.set()

    async def clean_up(self):
        tasks = asyncio.all_tasks()

        pending = [task for task in tasks if not task.done() and not task.get_name() == asyncio.current_task().get_name()]

        # await asyncio.gather(*pending)
