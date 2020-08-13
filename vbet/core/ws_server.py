from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING, Union

import websockets

from vbet.core import settings
from vbet.core.session import Session
from vbet.utils.log import get_logger

if TYPE_CHECKING:
    from vbet.core.vbet import Vbet


logger = get_logger('ws_server')


class WsServer:
    ws_server: Optional[websockets.WebSocketServer] = None
    sessions: Dict[int, Session] = {}
    session_index: int = 0
    app: Vbet

    def __init__(self, app: Vbet):
        self.app = app

    async def setup(self):
        logger.info(f'Starting the websocket server [{websockets.__version__}] url=ws://{settings.WS_HOST}:'
                    f'{settings.WS_PORT}')
        self.ws_server = await websockets.serve(self.handle, settings.WS_HOST, settings.WS_PORT)

    async def handle(self, websocket: websockets.WebSocketServerProtocol, path: str):
        WsServer.session_index += 1
        session_index = WsServer.session_index
        session = Session(self, session_index)  # type: Session
        self.sessions[session_index] = session
        logger.info(f'User connected {session_index}')
        await session.handler(websocket)
        self.sessions.pop(session_index)
        logger.info(f'User disconnected {session_index}')

    async def send_to_session(self, session_key: int, uri: str, body: Dict):
        session = self.sessions.get(session_key, None)  # type: Union[Session, None]
        if session:
            await session.send(uri, body)

    # Shutdown
    async def wait_closed(self):
        self.ws_server.close()
        await self.ws_server.wait_closed()
