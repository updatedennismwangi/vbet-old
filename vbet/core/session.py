from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, Dict, Optional, TYPE_CHECKING, Union

import websockets

from vbet.utils.log import get_logger
from vbet.utils.parser import decode_json, encode_json, inspect_ws_server_payload

if TYPE_CHECKING:
    from vbet.core.ws_server import WsServer


logger = get_logger('session')

SUDO_URI = {
    'exit': 'application',
    'add': 'manager',
    'login': 'manager',
    'check': 'manager'
}

CLIENT_URI = {'player': 'manager'}


class Session:
    def __init__(self, ws_server: WsServer, session_key: int, sudo=True):
        self.sudo: bool = sudo
        self.session_key: int = session_key
        self.ws_server: WsServer = ws_server
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None

    async def handler(self, websocket: websockets.WebSocketServerProtocol):
        self.websocket = websocket
        try:
            async for message in websocket:
                message = decode_json(message)  # type: Union[Dict, None]
                if isinstance(message, dict):
                    data = inspect_ws_server_payload(message)
                    if isinstance(data, tuple):
                        (uri, body) = data
                        target: Optional[str] = None
                        if uri in SUDO_URI:
                            if self.sudo:
                                target = SUDO_URI.get(uri)
                        elif uri in CLIENT_URI:
                            target = CLIENT_URI.get(uri)
                        if target:
                            asyncio.create_task(self.dispatch(target, uri, body))
                    else:
                        logger.warning('Invalid payload format')
                else:
                    logger.warning('Invalid payload')
        except websockets.ConnectionClosedError:
            pass

    async def send(self, uri: str, body: Dict):
        payload = {'uri': uri, 'body': body}
        await self.websocket.send(encode_json(payload))

    async def dispatch(self, target: str, uri: str, body: Dict):
        try:
            if target == 'application':
                callback = getattr(self.ws_server.app, f'{uri}_uri')  # type: Callable[[int, Dict], Coroutine[Any]]
                await callback(self.session_key, body)
            else:
                await self.ws_server.app.manager.ws_queue.put((self.session_key, uri, body))
        except asyncio.CancelledError:
            pass
