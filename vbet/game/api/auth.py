from vbet.utils.log import *
import aiohttp
from vbet.utils.exceptions import InvalidUserAuthentication, InvalidUserHash
import asyncio
from vbet.core import settings

logger = get_logger('auth')

HEADERS = {
    'User-Agent': '[vbet player: 1.0]'
}

WSS_URL = 'wss://virtual-proxy.golden-race.net:9443/vs'
if settings.API_NAME == settings.BETIKA:
    HASH_URL = 'https://api-golden-race.betika.com/betikagr/Login'
    LOGIN_URL = 'https://api.betika.com/v1/login'
    COOKIES_URL = 'https://api.betika.com'

    async def login_hash(username: str, user_id: int, socket_id: int, http: aiohttp.ClientSession):
        pin_hash = None
        while pin_hash is None:
            try:
                response = await http.post(HASH_URL, json={'profile_id': user_id})
                data = await response.json(content_type="text/json")
                if response.status == 200:
                    pin_hash = data.get('onlineHash', None)
                    if pin_hash:
                        return pin_hash
                    else:
                        raise InvalidUserHash(username, response.status, data)
            except aiohttp.ClientConnectionError as err:
                logger.error(f'[{username}:{socket_id}] get-hash {err}')
                await asyncio.sleep(30)
            except InvalidUserHash as err:
                await asyncio.sleep(30)
                logger.error(err)


    async def login_password(username: str, password: str, http: aiohttp.ClientSession):
        unit_id = None
        token = None
        while unit_id is None:
            try:
                payload = {'mobile': username, 'password': password, 'remember': True, 'src': 'DESKTOP'}
                response = await http.post(LOGIN_URL, json=payload)
                data = await response.json(content_type="application/json")
                if response.status == 200:
                    token = data.get('token')
                    if not token:
                        raise InvalidUserAuthentication(username, password,
                                                        InvalidUserAuthentication.UNKNOWN_ERROR, body=data)
                    user_data = data.get('data')
                    user = user_data.get('user')
                    unit_id = user.get('id')
                    return unit_id, token
                else:
                    raise InvalidUserAuthentication(username, password,
                                                    InvalidUserAuthentication.INVALID_CREDENTIALS, body=data)
            except aiohttp.ClientConnectionError as err:
                logger.error(f'[{username}] login user timeout {err}')
                await asyncio.sleep(30)

else:
    HASH_URL = 'https://www.mozzartbet.co.ke/golden-race-me'
    LOGIN_URL = 'https://www.mozzartbet.co.ke/auth'
    COOKIES_URL = 'https://www.mozzartbet.co.ke'

    async def login_hash(username: str, user_id: int, socket_id: int, http: aiohttp.ClientSession):
        pin_hash = None
        while pin_hash is None:
            try:
                response = await http.get(HASH_URL)
                data = await response.json(content_type="application/json")
                if response.status == 200:
                    pin_hash = data.get('onlineHash', None)
                    if pin_hash:
                        session_id = data.get('session_id', None)
                        return pin_hash
                    else:
                        raise InvalidUserHash(username, response.status, data)
            except aiohttp.ClientConnectionError as err:
                logger.error(f'[{username}:{socket_id}] get-hash {err}')
                await asyncio.sleep(30)
            except InvalidUserHash as err:
                await asyncio.sleep(30)
                logger.error(err)


    async def login_password(username: str, password: str, http: aiohttp.ClientSession):
        unit_id = None
        token = None
        while unit_id is None:
            try:
                fingerprint = 'a39ad90130543e3547bf7b2bda9369'
                payload = {'fingerprint': fingerprint, 'isCasinoPage': False, 'password': password, 'username':
                    username}
                response = await http.post(LOGIN_URL, json=payload)
                data = await response.json(content_type="application/json")
                if response.status == 200:
                    status = data.get('status')
                    if not status:
                        raise InvalidUserAuthentication(username, password,
                                                        InvalidUserAuthentication.UNKNOWN_ERROR, body=data)
                    user = data.get('user')
                    unit_id = user.get('userId')
                    return unit_id, token
                else:
                    raise InvalidUserAuthentication(username, password,
                                                    InvalidUserAuthentication.INVALID_CREDENTIALS, body=data)
            except aiohttp.ClientConnectionError as err:
                logger.error(f'[{username}] login user timeout {err}')
                await asyncio.sleep(30)




