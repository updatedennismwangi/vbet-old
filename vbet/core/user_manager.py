from vbet.utils.log import *
from vbet.utils.parser import decode_json, encode_json
from vbet.utils import exceptions
from vbet.game.user import User
from vbet.game.api.auth import login_password, HEADERS, COOKIES_URL
from vbet.core import settings
from typing import Any, Dict, List, Tuple
import aioredis
import asyncio
import aiohttp


logger = get_logger('user_manager')


class UserManager:
    def __init__(self, app):
        self.app = app
        self.users: Dict[str, User] = {}
        self.validating_users: Dict[str, Dict] = {}
        self.login_users: Dict[str, Dict] = {}
        self.ws_queue = asyncio.Queue()
        self.ws_reader_future: asyncio.Future = None
        self.loop: asyncio.BaseEventLoop = None
        self.redis: aioredis.ConnectionsPool = None

    async def init(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.redis = await aioredis.create_pool(settings.REDIS_URI)
        self.ws_reader_future = loop.create_task(self.ws_reader())

    def send_to_session(self, session_key: int, uri: str, body: Dict):
        asyncio.create_task(self.app.ws_server.send_to_session(session_key, uri, body))

    async def validate_user(self, username: str):
        cache_data = await self.redis.execute('get', f'{settings.API_NAME}_session_{username}')
        if cache_data:
            data = decode_json(cache_data.decode('utf-8'))
            cookies = data.get('cookies')
            unit_id = data.get('id')
            token = data.get('token')
            http = aiohttp.ClientSession(cookies=cookies, headers=HEADERS)
            return [username, unit_id, token, http]
        else:
            raise exceptions.InvalidUserCache(username)

    async def login_user(self, username: str, password: str):
        http = aiohttp.ClientSession(headers=HEADERS)
        unit_id, token = await login_password(username, password, http)
        cookies = http.cookie_jar.filter_cookies(COOKIES_URL)
        if settings.API_NAME == settings.MOZART:
            _cookies = {}
            for k, v in cookies.items():
                _cookies[k] = v.value
            cookies = _cookies
        data = {
            'cookies': cookies,
            'id': unit_id,
            'token': token
        }
        await self.redis.execute('set', f'{settings.API_NAME}_session_{username}', encode_json(data))
        logger.info(f'[{username}] user cached {cookies}')
        await http.close()
        return username, data

    def user_validation_callback(self, future: asyncio.Future):
        exc = future.exception()
        if isinstance(exc, exceptions.InvalidUserCache):
            logger.warning(f'Error validate user {exc}')
            validate_payload = self.validating_users.pop(exc.username, None)
            session_key = validate_payload.get('session_key')
            if session_key:
                self.send_to_session(session_key, 'add', {'error': exc.__str__()})
        else:
            data = future.result()
            username, unit_id, token, http = data[0], data[1], data[2], data[3]
            try:
                validate_payload = self.validating_users.pop(username, None)
                validate_data = validate_payload.get('body')
            except KeyError:
                pass
            else:
                validate_data.setdefault('unit_id', unit_id)
                validate_data.setdefault('token', token)
                validate_data.setdefault('http', http)
                self.create_user(username, validate_data)
                session_key = validate_payload.get('session_key')
                if session_key:
                    self.send_to_session(session_key, 'add', {'id': unit_id, 'username': username})

    def user_login_callback(self, future: asyncio.Future):
        exc = future.exception()
        if isinstance(exc, exceptions.InvalidUserAuthentication):
            logger.warning(f'Error login user {exc}')
            login_payload = self.login_users.pop(exc.username, None)
            session_key = login_payload.get('session_key')
            if session_key:
                self.send_to_session(session_key, 'login', {'error': exc.body})
        else:
            data = future.result()
            username, user_data = data[0], data[1]
            login_payload = self.login_users.pop(username, None)
            session_key = login_payload.get('session_key')
            if session_key:
                self.send_to_session(session_key, 'login', user_data)

    def create_user(self, username, login_data: Dict):
        games = login_data.get('games')
        http = login_data.get('http')
        token = login_data.get('token')
        unit_id = login_data.get('unit_id')
        demo = login_data.get('demo')
        self.users[username] = User(username, demo, self)
        user = self.users.get(username)
        valid_games = [int(game) for game in games]
        user.games = valid_games
        user.set_api_data(unit_id, token, http)
        user.online()

    async def add_uri(self, session_key: int, body: Dict):
        username = body.get('username')
        user = self.users.get(username, None)
        validating_user = self.validating_users.get(username, None)
        if not user and not validating_user:
            future = self.loop.create_task(self.validate_user(username))
            future.add_done_callback(self.user_validation_callback)
            self.validating_users[username] = {'future': future, 'session_key': session_key, 'body': body}

    async def login_uri(self, session_key: int, body: Dict):
        username = body.get('username')
        password = body.get('password')
        if username not in self.login_users:
            future = self.loop.create_task(self.login_user(username, password))
            future.add_done_callback(self.user_login_callback)
            self.login_users[username] = {'future': future, 'body': body, 'session_key': session_key}

    async def player_uri(self, session_key: int, body: Dict):
        username = body.get('username')
        player = body.get('player')
        odd_id = body.get('odd_id')
        games = body.get('games')
        user = self.users.get(username, None)
        if user:
            user.modify_player(player, odd_id, games)

    async def ws_reader(self):
        while True:
            payload = await self.ws_queue.get()
            session_key, uri, body = payload[0], payload[1], payload[2]
            callback = getattr(self, f'{uri}_uri')
            asyncio.get_event_loop().create_task(callback(session_key, body))

    async def cancel_ws_reader(self):
        if asyncio.isfuture(self.ws_reader_future):
            if not self.ws_reader_future.done():
                self.ws_reader_future.cancel()
                try:
                    await self.ws_reader_future
                except asyncio.CancelledError:
                    pass

    async def exit(self):
        pending = {}
        for username, user in self.users.items():
            await user.exit()
            pending[username] = asyncio.create_task(user.close_event.wait())
        if pending:
            done, p = await asyncio.wait(list(pending.values()), return_when=asyncio.ALL_COMPLETED)

    async def wait_closed(self):
        self.shutdown()
        await self.exit()
        self.redis.close()
        await self.redis.wait_closed()
        await self.cancel_ws_reader()

    def shutdown(self):
        pass
