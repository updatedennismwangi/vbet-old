from vbet.utils.log import *
import websockets
import asyncio
from vbet.core import settings
from typing import Dict
from vbet.core.session import Session


logger = get_logger('ws_server')


class WsServer:
    def __init__(self, app):
        self.app = app
        self.ws_server: websockets.WebSocketServer = None
        self.sessions: Dict[int, Session] = {}
        self._session_index = 0
        self._session_index_lock = asyncio.Lock()

    @property
    async def session_index(self):
        async with self._session_index_lock:
            self._session_index += 1
        return self._session_index

    def setup(self):
        logger.info(f'Starting the websocket server [{websockets.__version__}]')
        serve = websockets.serve(self.handle, settings.WS_HOST, settings.WS_PORT)
        self.ws_server = asyncio.get_event_loop().run_until_complete(serve)

    async def handle(self, websocket: websockets.WebSocketServerProtocol, path):
        session_index = await self.session_index
        session = Session(self, session_index)
        self.sessions[session_index] = session
        logger.info(f'User connected {session_index}')
        await session.handler(websocket)
        self.sessions.pop(session_index)
        logger.info(f'User disconnected {session_index}')

    async def send_to_session(self, session_key: int, uri: str, body: Dict):
        session = self.sessions.get(session_key, None)
        if session:
            await session.send(uri, body)

    async def manager_uri(self, session_key: int, uri: str, body: Dict):
        await self.app.manager.ws_queue.put([session_key, uri, body])

    async def application_uri(self, session_key: int, uri: str, body: Dict):
        callback = getattr(self.app, f'{uri}_uri')
        await callback(session_key, body)

    async def wait_closed(self):
        self.shutdown()
        await self.ws_server.wait_closed()

    def shutdown(self):
        self.ws_server.close()
