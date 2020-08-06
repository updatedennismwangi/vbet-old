from vbet.utils.log import get_logger, async_exception_logger, exception_logger
from vbet.utils.parser import decode_json, encode_json, UserResource, Resource, inspect_websocket_response
from vbet.game.api.auth import login_hash, WSS_URL
from vbet.core import settings
import asyncio
from typing import Dict, List, Tuple
import aiohttp
import websockets
import time
import socket

logger = get_logger('socket')


COMPETITION_SOCKET = 0
TICKET_SOCKET = 1


class Socket:
    HASH = 0
    CONNECTING = 1
    CONNECTED = 2
    NOT_AUTHORIZED = 3
    CLOSED = 4
    READY = 5

    CLOSE_TIMEOUT = 40
    LOGIN_CLOSE_TIMEOUT = 10
    LOGIN_RETRY_TIMEOUT = 5

    CLOSE_CODE = 100
    LOGIN_TIMEOUT_CODE = 101
    MESSAGE_TIMEOUT_CODE = 102
    ERROR_CODE = 103

    def __init__(self, user, socket_id: int, mode=COMPETITION_SOCKET, host: str = None):
        self.alive = True
        self.user = user
        self.socket_id = socket_id
        self.xs: int = -1
        self.max_xs: int = 10000000
        self.client_id: str = ''
        self.status = Socket.CLOSED
        self.close_timeout = Socket.CLOSE_TIMEOUT
        self.connected = False
        self.authorized = False
        self.hash_future: asyncio.Future = None
        self.event_loop_future: asyncio.Future = None
        self.online_hash: str = ''
        self._socket: websockets.WebSocketClientProtocol = None
        self.error_code = Socket.CLOSE_CODE
        self.profile = 'WEB'
        self.mode = COMPETITION_SOCKET
        self.last_used: float = time.time()
        self.host: str = host

    def connect_callback(self, future: asyncio.Future):
        if not self.alive:
            asyncio.create_task(self.user.socket_offline(self.socket_id))
        else:
            if not future.cancelled():
                result = future.result()
                self.status = Socket.CONNECTING
                self.online_hash = result
                self.event_loop_future = asyncio.create_task(self.event_loop())
                self.event_loop_future.add_done_callback(self.event_loop_callback)
            else:
                pass
                # asyncio.create_task(self.user.socket_offline(self.socket_id))

    def event_loop_callback(self, future: asyncio.Future):
        self.authorized = False
        self.connected = False
        if self._socket is not None:
            if not self._socket.closed:
                asyncio.create_task(self._socket.close())
        if self.alive:
            asyncio.create_task(self.user.socket_lost(self.socket_id))
            logger.debug(f'[{self.user.username}:{self.socket_id}] restarting socket')
            self.connect()
        else:
            asyncio.create_task(self.user.socket_offline(self.socket_id))

    def connect(self):
        self.status = Socket.HASH

        self.hash_future = asyncio.get_event_loop().create_task(login_hash(self.user.username, self.user.user_id,
                                                                           self.socket_id, self.user.http))
        self.hash_future.add_done_callback(self.connect_callback)

    @async_exception_logger('error')
    async def event_loop(self):
        retry_connect = True
        while retry_connect:
            self.error_code = Socket.CLOSE_CODE
            retry_connect = False
            try:
                self.authorized = False
                logger.info(f'[{self.user.username}:{self.socket_id}] opening socket [{self.online_hash}]')
                if not self.host:
                    self.host = 'virtual-proxy.golden-race.net'
                async with websockets.connect(WSS_URL, close_timeout=2, host=self.host, port=9443) as sock:
                    self.status = Socket.CONNECTED
                    self._socket = sock
                    self.client_id = ''
                    self.connected = True
                    logger.debug(f'[{self.user.username}:{self.socket_id}] socket connected ['
                                 f'{self.online_hash}:{self._socket.remote_address}]')
                    await self.login()
                    # Socket authorization
                    self.close_timeout = Socket.LOGIN_CLOSE_TIMEOUT
                    message = await self.reader(self.close_timeout)
                    if message:
                        await self.process_message(message)

                        # Normal message processing
                        self.close_timeout = Socket.CLOSE_TIMEOUT
                        while True:
                            message = await self.reader(self.close_timeout)
                            if message:
                                await self.process_message(message)
                            else:
                                if self.error_code == Socket.MESSAGE_TIMEOUT_CODE:
                                    if self.mode == COMPETITION_SOCKET:
                                        await self.sync()
                                    else:
                                        await self.get_last_tickets()
                                    message = await self.reader(20)
                                    if message:
                                        await self.process_message(message)
                                    else:
                                        if self.error_code == Socket.MESSAGE_TIMEOUT_CODE:
                                            logger.debug(f'[{self.user.username}:{self.socket_id}] socket message timeout')
                                        break
                                elif self.error_code == Socket.ERROR_CODE or self.error_code == Socket.CLOSE_CODE:
                                    break
                    else:
                        if self.error_code == Socket.MESSAGE_TIMEOUT_CODE:
                            self.error_code = Socket.LOGIN_TIMEOUT_CODE
                            logger.warning(f'[{self.user.username}:{self.socket_id}] socket login timeout')
                        elif self.error_code == Socket.ERROR_CODE or self.error_code == Socket.CLOSE_CODE:
                            break

                logger.debug(f'[{self.user.username}:{self.socket_id}] socket disconnected [{self.online_hash}:'
                             f'{self._socket.remote_address}]')
                self.connected = False
            except (aiohttp.ClientConnectionError, socket.gaierror, websockets.InvalidHandshake) as err:
                retry_connect = True
                logger.warning(f'[{self.user.username}:{self.socket_id}] websocket connection failed {err}')
                await asyncio.sleep(Socket.LOGIN_RETRY_TIMEOUT)

    async def process_message(self, message: str):
        message = decode_json(message)
        xs, resource, valid_response, body = inspect_websocket_response(message)
        # logger.debug(f'[{self.user.username}:{self.socket_id}] {resource} Response')
        if resource == Resource.LOGIN:
            await self.login_callback(valid_response, body)
        else:
            await self.user.receive(self.socket_id, xs, resource, valid_response, body)

    async def login(self):
        login_body = {
            'onlineHash': self.online_hash,
            'profile': self.profile
        }
        self.send(Resource.LOGIN, query=login_body)

    async def sync(self):
        if self.user.sync_enabled:
            self.send(Resource.SYNC, {})

    async def get_last_tickets(self):
        payload = self.user.get_ticket_by_id(10)
        self.send(Resource.TICKETS_FIND_BY_ID, query=payload)

    async def login_callback(self, valid_response: bool, body: Dict):
        if valid_response and isinstance(body, dict):
            client_id = body.get('clientId', None)
            if client_id:
                self.client_id = client_id
                logger.info(f'[{self.user.username}:{self.socket_id}] socket auth success [{self.online_hash}]')
                await self.user.setup_session(body)
                await self.login_success()
            else:
                await self.login_failed(body)
        else:
            await self.login_failed(body)

    async def login_failed(self, body: Dict):
        logger.error(f'[{self.user.username}:{self.socket_id}] authentication failed [{self.online_hash}] {body}')
        self.status = Socket.NOT_AUTHORIZED
        await self._socket.close()

    async def login_success(self):
        self.authorized = True
        self.status = Socket.READY
        asyncio.create_task(self.user.socket_online(self.socket_id))

    def send(self, resource: str, query=None, body=None) -> int:
        if self.connected:
            self.xs += 1
            if query is not None:
                method = 'GET'
            else:
                method = 'POST'
                query = {}
            headers = {'Content-Type': 'application/json'}
            if resource != Resource.LOGIN:
                headers['clientId'] = self.client_id
            data = {
                'type': 'REQUEST',
                'xs': self.xs,
                'ts': int(time.time() * 1000),
                'req': {
                    'method': method,
                    'query': query,
                    'headers': headers,
                    'resource': resource,
                    'basePath': '/api/client/v0.1',
                    'host': 'wss://virtual-proxy.golden-race.net:9443'
                }
            }
            if method == "POST":
                data['req']['body'] = body
            asyncio.create_task(self._send(resource, data))
            return self.xs
        return -1

    async def reader(self, timeout: float):
        payload = None
        try:
            payload = await asyncio.wait_for(self._reader(), timeout=timeout)
        except asyncio.TimeoutError:
            self.error_code = Socket.MESSAGE_TIMEOUT_CODE
        except websockets.ConnectionClosed as err:
            if isinstance(err, websockets.ConnectionClosedError):
                self.error_code = Socket.ERROR_CODE
                logger.warning(f'[{self.user.username}:{self.socket_id}] websocket connection error : {err.code} '
                               f'{err.reason}')
            else:
                self.error_code = Socket.CLOSE_CODE
                logger.debug(f'[{self.user.username}:{self.socket_id}] websocket connection closed')
        finally:
            return payload

    async def _reader(self):
        return await self._socket.recv()

    async def _send(self, resource: str, body: Dict):
        # logger.debug(f'[{self.user.username}:{self.socket_id}] {resource} Request')
        try:
            p = encode_json(body)
            await self._socket.send(p)
        except websockets.ConnectionClosed:
            pass

    async def exit(self):
        self.alive = False
        if self.connected:
            await self._socket.close()

    def shutdown(self):
        if asyncio.isfuture(self.hash_future):
            if not self.hash_future.done():
                self.hash_future.cancel()

        if asyncio.isfuture(self.event_loop_future):
            if not self.event_loop_future.done():
                self.event_loop_future.cancel()

