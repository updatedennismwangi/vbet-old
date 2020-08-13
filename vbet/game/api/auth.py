import asyncio
from typing import Dict, Optional

import aiohttp

import vbet
from vbet.core import settings
from vbet.utils.exceptions import InvalidUserAuthentication, InvalidUserHash
from vbet.utils.log import get_logger

logger = get_logger('auth')


HEADERS = {
    f'User-Agent': f'[vbet : {vbet.__VERSION__}]'
}


WSS_URL = 'wss://virtual-proxy.golden-race.net:9443/vs'
if settings.API_NAME == settings.BETIKA:
    HASH_URL = 'https://api-golden-race.betika.com/betikagr/Login'
    LOGIN_URL = 'https://api.betika.com/v1/login'
    COOKIES_URL = 'https://api.betika.com'

    async def login_hash(username: str, user_id: int, socket_id: int, http: aiohttp.ClientSession):
        pin_hash: Optional[str] = None
        while pin_hash is None:
            try:
                response = await http.post(HASH_URL, json={'profile_id': user_id})  # type: aiohttp.ClientResponse
                data = await response.json(content_type="text/json")  # type: Dict
                if response.status == 200:
                    pin_hash = data.get('onlineHash', None)  # type: Optional[str]
                    if isinstance(pin_hash, str):
                        return pin_hash
                    else:
                        raise InvalidUserHash(username, response.status, body=data)
            except (aiohttp.ClientConnectionError, InvalidUserHash) as err:
                logger.error(f'[{username}:{socket_id}] get-hash {err}')
                await asyncio.sleep(30)


    async def login_password(username: str, password: str, http: aiohttp.ClientSession):
        unit_id: Optional[int] = None
        token: Optional[str] = None
        while unit_id is None:
            try:
                payload = {'mobile': username, 'password': password, 'remember': True, 'src': 'DESKTOP'}
                response = await http.post(LOGIN_URL, json=payload)  # type: aiohttp.ClientResponse
                data = await response.json(content_type="application/json")  # type: Dict
                if response.status == 200:
                    token = data.get('token', None)  # type: Optional[str]
                    user_data = data.get('data', {})  # type: Dict
                    user = user_data.get('user', {})  # type: Dict
                    unit_id = user.get('id', None)  # type: Optional[int]
                    if not token or not unit_id:
                        raise InvalidUserAuthentication(username, password,
                                                        InvalidUserAuthentication.UNKNOWN_ERROR, body=data)
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
        pin_hash: Optional[str] = None
        while pin_hash is None:
            try:
                response = await http.get(HASH_URL)  # type: aiohttp.ClientResponse
                data = await response.json(content_type="application/json")  # type: Dict
                if response.status == 200:
                    pin_hash = data.get('onlineHash', None)  # type: Optional[str]
                    if isinstance(pin_hash, str):
                        return pin_hash
                    else:
                        raise InvalidUserHash(username, response.status, body=data)
            except (aiohttp.ClientConnectionError, InvalidUserHash) as err:
                logger.error(f'[{username}:{socket_id}] get-hash {err}')
                await asyncio.sleep(30)

    async def login_password(username: str, password: str, http: aiohttp.ClientSession):
        unit_id: Optional[int] = None
        token: Optional[str] = None
        while unit_id is None:
            try:
                fingerprint = 'a39ad90130543e3547bf7b2bda9369'
                body = {'fingerprint': fingerprint, 'isCasinoPage': False, 'password': password, 'username': username}
                response = await http.post(LOGIN_URL, json=body)  # type: aiohttp.ClientResponse
                data = await response.json(content_type="application/json")  # type: Dict
                if response.status == 200:
                    status = data.get('status', None)  # type: Optional[str]
                    if isinstance(status, str):
                        raise InvalidUserAuthentication(username, password,
                                                        InvalidUserAuthentication.UNKNOWN_ERROR, body=data)
                    user = data.get('user', {})  # type: Dict
                    unit_id = user.get('userId', None)  # type: Optional[int]
                    return unit_id, token
                else:
                    raise InvalidUserAuthentication(username, password,
                                                    InvalidUserAuthentication.INVALID_CREDENTIALS, body=data)
            except aiohttp.ClientConnectionError as err:
                logger.error(f'[{username}] login user timeout {err}')
                await asyncio.sleep(30)




