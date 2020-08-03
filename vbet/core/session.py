from vbet.utils.log import *
from typing import Any, Dict
import asyncio
from vbet.utils.parser import inspect_ws_server_payload, decode_json
import websockets

logger = get_logger('session')

SUDO_URI = ['exit', 'add']
CLIENT_URI = ['player']


class Session:
    def __init__(self, ws_server, sudo=True):
        self.sudo = sudo
        self.ws_server = ws_server

    async def handler(self, websocket: websockets.WebSocketServerProtocol):
        try:
            async for message in websocket:
                asyncio.create_task(self.dispatch(message))
        except websockets.ConnectionClosedError:
            pass

    @async_exception_logger('session')
    async def dispatch(self, message: Any):
        message = decode_json(message)
        if isinstance(message, dict):
            uri, body = inspect_ws_server_payload(message)
            if uri:
                if uri in SUDO_URI:
                    if self.sudo:
                        callback = getattr(self, f'uri_{uri}')
                        await callback(body)
                elif uri in CLIENT_URI:
                    callback = getattr(self, f'uri_{uri}')
                    await callback(body)
            else:
                logger.warning('Invalid payload format')
        else:
            logger.warning('Invalid payload')

    async def uri_exit(self, body: Dict):
        callback = getattr(self.ws_server, 'application_uri')
        await callback('exit', body)

    async def uri_add(self, body: Dict):
        callback = getattr(self.ws_server, 'manager_uri')
        await callback('add', body)

    async def uri_player(self, body: Dict):
        callback = getattr(self.ws_server, 'manager_uri')
        await callback('player', body)
