from vbet.utils.log import *
from typing import Any, Dict
import asyncio
from vbet.utils.parser import inspect_ws_server_payload, decode_json, encode_json
import websockets

logger = get_logger('session')

SUDO_URI = {
    'exit': 'application',
    'add': 'manager',
    'login': 'manager',
    'check': 'manager'}
CLIENT_URI = {'player': 'manager'}


class Session:
    def __init__(self, ws_server, session_key: int, sudo=True):
        self.sudo = sudo
        self.session_key = session_key
        self.ws_server = ws_server
        self.websocket: websockets.WebSocketServerProtocol = None

    async def handler(self, websocket: websockets.WebSocketServerProtocol):
        self.websocket = websocket
        try:
            async for message in websocket:
                asyncio.create_task(self.dispatch(message))
        except websockets.ConnectionClosedError:
            pass

    async def dispatch(self, message: Any):
        message = decode_json(message)
        if isinstance(message, dict):
            uri, body = inspect_ws_server_payload(message)
            if uri:
                target = None
                if uri in SUDO_URI:
                    if self.sudo:
                        target = SUDO_URI.get(uri)
                elif uri in CLIENT_URI:
                    target = CLIENT_URI.get(uri)
                if target:
                    callback = getattr(self.ws_server, f'{target}_uri')
                    await callback(self.session_key, uri, body)
            else:
                logger.warning('Invalid payload format')
        else:
            logger.warning('Invalid payload')

    async def send(self, uri: str, body: Dict):
        payload = {'uri': uri, 'body': body}
        await self.websocket.send(encode_json(payload))
