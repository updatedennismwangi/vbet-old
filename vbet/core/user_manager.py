from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, TYPE_CHECKING, Union

import aiohttp
import aioredis

from vbet.core import settings
from vbet.game.api.auth import COOKIES_URL, HEADERS, login_password
from vbet.game.user import User
from vbet.utils import exceptions
from vbet.utils.log import get_logger
from vbet.utils.parser import decode_json, encode_json

if TYPE_CHECKING:
    from vbet.core.vbet import Vbet


logger = get_logger('user_manager')


class UserManager:
    users: Dict[str, User] = {}
    validating_users: Dict[str, Dict] = {}
    login_users: Dict[str, Dict] = {}
    ws_queue: asyncio.Queue = asyncio.Queue()
    ws_reader_future: Optional[asyncio.Future] = None
    redis: Optional[aioredis.ConnectionsPool] = None
    app: Vbet

    def __init__(self, app: Vbet):
        self.app = app

    async def setup(self):
        self.redis = await aioredis.create_pool(settings.REDIS_URI)
        self.ws_reader_future = asyncio.create_task(self.ws_reader())

    # Ws server
    def send_to_session(self, session_key: int, uri: str, body: Dict):
        asyncio.create_task(self.app.ws_server.send_to_session(session_key, uri, body))

    async def ws_reader(self):
        try:
            while True:
                payload = await self.ws_queue.get()  # type: Union[Tuple[int, str, Any], None]
                if payload:
                    (session_key, uri, body) = payload
                    callback = getattr(self, f'{uri}_uri')  # type: Callable[[int, Dict], Coroutine[Any]]
                    asyncio.create_task(callback(session_key, body))
                else:
                    break
        except asyncio.CancelledError:
            pass

    async def cancel_ws_reader(self):
        if asyncio.isfuture(self.ws_reader_future):
            if not self.ws_reader_future.done():
                self.ws_reader_future.cancel()
                try:
                    await self.ws_reader_future
                except asyncio.CancelledError:
                    pass

    # User management
    async def validate_user(self, username: str) -> Optional[Tuple[str, int, str, aiohttp.ClientSession]]:
        cache_id = f'{settings.API_NAME}_session_{username}'
        cache_data = await self.redis.execute('get', cache_id)  # type: Union[str, bytes, None]
        if cache_data:
            data = decode_json(cache_data.decode('utf-8'))  # type: Dict
            cookies = data.get('cookies')  # type: Dict
            unit_id = data.get('id')  # type: int
            token = data.get('token')  # type: str
            http = aiohttp.ClientSession(cookies=cookies, headers=HEADERS)  # type: aiohttp.ClientSession
            return username, unit_id, token, http
        else:
            raise exceptions.InvalidUserCache(username)

    async def login_user(self, username: str, password: str) -> Optional[Tuple[str, Dict]]:
        http = aiohttp.ClientSession(headers=HEADERS)  # type: aiohttp.ClientSession
        unit_id, token = await login_password(username, password, http)  # type: Optional[Tuple[int, str]]
        cookies = http.cookie_jar.filter_cookies(COOKIES_URL)  # type: Dict
        if settings.API_NAME == settings.MOZART:
            _cookies = {}  # type: Dict
            for cookie_name, cookie_value in cookies.items():
                _cookies[cookie_name] = cookie_value
            cookies = _cookies
        data = {'cookies': cookies, 'id': unit_id, 'token': token}  # type: Dict
        cache_id = f'{settings.API_NAME}_session_{username}'
        await self.redis.execute('set', cache_id, encode_json(data))
        logger.info(f'[{username}] user cached {cookies}')
        await http.close()
        return username, data

    def user_validation_callback(self, future: asyncio.Future):
        exc = future.exception()  # TODO: Type checks
        if isinstance(exc, exceptions.InvalidUserCache):
            logger.warning(f'{exc}')
            validate_payload = self.validating_users.pop(exc.username, None)  # type: Union[Dict, None]
            session_key = validate_payload.get('session_key')  # type: int
            if session_key:
                self.send_to_session(session_key, 'add', {'error': exc.__str__()})
        else:
            data = future.result()  # type: Tuple[str, int, str, aiohttp.ClientSession]
            (username, unit_id, token, http) = data
            try:
                validate_payload = self.validating_users.pop(username, None)  # type: Union[Dict, None]
                validate_data = validate_payload.get('body')  # type: Dict
            except KeyError:
                pass
            else:
                validate_data.setdefault('unit_id', unit_id)
                validate_data.setdefault('token', token)
                validate_data.setdefault('http', http)
                user = self.create_user(username, validate_data)  # type: User
                session_key = validate_payload.get('session_key')  # type: int
                if session_key:
                    self.send_to_session(session_key, 'add', {'id': unit_id, 'username': user.username})

    def user_login_callback(self, future: asyncio.Future):
        exc = future.exception()  # TODO: Type checks
        if isinstance(exc, exceptions.InvalidUserAuthentication):
            logger.warning(f'Error login user {exc}')
            login_payload = self.login_users.pop(exc.username, None)  # type: Union[Dict, None]
            session_key = login_payload.get('session_key')  # type: int
            if session_key:
                self.send_to_session(session_key, 'login', {'error': exc.body})
        else:
            data = future.result()  # type: Tuple[str, Dict]
            username, user_data = data[0], data[1]
            login_payload = self.login_users.pop(username, None)  # type: Union[Dict, None]
            session_key = login_payload.get('session_key')  # type: int
            if session_key:
                self.send_to_session(session_key, 'login', user_data)

    def create_user(self, username: str, login_data: Dict) -> User:
        games = login_data.get('games')  # type: List[int]
        http = login_data.get('http')  # type: aiohttp.ClientSession
        token = login_data.get('token')  # type: str
        unit_id = login_data.get('unit_id')  # type: int
        demo = login_data.get('demo')  # type: bool
        self.users[username] = User(self, username, demo,)
        user = self.users.get(username)  # type: User
        user.games = games
        user.set_api_data(unit_id, token, http)
        user.online()
        return user

    # API calls
    async def add_uri(self, session_key: int, body: Dict):
        username = body.get('username', None)  # type: Union[str, Any,]
        if isinstance(username, str):
            user = self.users.get(username, None)  # type: Union[User, None]
            validating_user = self.validating_users.get(username, None)  # type: Union[Dict, None]
            if not user and not validating_user:
                future = asyncio.create_task(self.validate_user(username))  # type: asyncio.Future
                future.add_done_callback(self.user_validation_callback)
                self.validating_users[username] = {'future': future, 'session_key': session_key, 'body': body}

    async def login_uri(self, session_key: int, body: Dict):
        username = body.get('username', None)  # type: Union[str, Any]
        password = body.get('password', None)  # type: Union[str, Any]
        if isinstance(username, str) and isinstance(password, str):
            if username not in self.login_users:
                future = asyncio.create_task(self.login_user(username, password))  # type: asyncio.Future
                future.add_done_callback(self.user_login_callback)
                self.login_users[username] = {'future': future, 'body': body, 'session_key': session_key}

    # TODO: Implement player_uri or do away with the api
    # TODO: Type checks
    async def player_uri(self, session_key: int, body: Dict):
        username = body.get('username')
        player = body.get('player')
        odd_id = body.get('odd_id')
        games = body.get('games')
        user = self.users.get(username, None)
        if user:
            user.modify_player(player, odd_id, games)

    # Shutdown
    async def wait_closed(self):
        pending = {}  # type: Dict
        for username, user in self.users.items():
            pending[username] = asyncio.create_task(user.exit())
        if pending:
            done, p = await asyncio.wait(list(pending.values()), return_when=asyncio.ALL_COMPLETED)

        self.redis.close()  # close redis
        await self.redis.wait_closed()
        await self.cancel_ws_reader()  # cancel ws_queue reader
