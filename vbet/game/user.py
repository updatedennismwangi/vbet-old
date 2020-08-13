from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union

import aiofile
import aiohttp

from vbet.core import settings
from vbet.game.socket import Socket
from vbet.utils.log import get_logger
from vbet.utils.parser import decode_json, encode_json, get_ticket_timestamp, Resource
from .accounts import AccountManager
from .competition import LeagueCompetition
from .tickets import Ticket, TicketManager

if TYPE_CHECKING:
    from vbet.core.user_manager import UserManager

logger = get_logger('user')


class GameSettings:
    def __init__(self):
        self._odd_settings_id: int = 0
        self._playlists: Dict[int, Dict] = {}
        self._taxes_settings: Dict = {}
        self._game_settings: Dict = {}
        self._unit_id: Optional[int] = None
        self._ext_id = None
        self._ext_data = None
        self._player_name: Optional[str] = None
        self._currency: Dict = {}
        self.configured: bool = False

    @property
    def playlists(self):
        return self._playlists

    @property
    def odd_settings_id(self):
        return self._odd_settings_id

    @odd_settings_id.setter
    def odd_settings_id(self, odd_settings_id: int):
        self._odd_settings_id = odd_settings_id

    @property
    def taxes_settings_id(self):
        return self._taxes_settings

    @taxes_settings_id.setter
    def taxes_settings_id(self, taxes_settings_id):
        self._taxes_settings = taxes_settings_id.get('taxesSettingsId')

    @property
    def unit_id(self):
        return self._unit_id

    @property
    def ext_id(self):
        return self._ext_id

    @property
    def ext_data(self):
        return self._ext_data

    @ext_data.setter
    def ext_data(self, ext_data):
        self._ext_data = ext_data

    @property
    def player_name(self):
        return self._player_name

    @property
    def currency(self):
        return self._currency

    def process_displays(self, displays: List):
        self._playlists = {}
        for display in displays:
            content = display.get('content')
            playlist_id = content.get('playlistId')
            self._playlists[playlist_id] = content

    def process_game_settings(self, game_settings):
        for game_setting in game_settings:
            game_type = game_setting.get('gameType')
            val = game_type.get('val')
            limits = game_setting.get('limits')[0]
            currency = limits.get('currencyCode')
            max_stake = limits.get('maxStake')
            min_stake = limits.get('minStake')
            max_payout = limits.get('maxPayout')
            self._game_settings[val] = {
                'currency': currency,
                'min_stake': min_stake,
                'max_stake': max_stake,
                'max_payout': max_payout
            }

    def process_localization(self, localization: Dict):
        self._currency = localization.get('currencySett').get('currency')

    def process_auth(self, auth: Dict):
        self._unit_id = auth.get('unit').get('id')
        self._ext_id = auth.get('unit').get('extId')
        self._player_name = auth.get('unit').get('name')

    def get_val_settings(self, val: str) -> Dict:
        return self._game_settings.get(val, {})


class User:
    def __init__(self, manager: UserManager, username: str, demo: bool):
        self.username: str = username
        self.manager: UserManager = manager
        self.demo: bool = demo
        self.http: Optional[aiohttp.ClientSession, None] = None
        self.token: Optional[str, None] = None
        self.user_id: Optional[int, None] = None
        self.active: bool = False
        self.active_event: asyncio.Event = asyncio.Event()
        self.close_event: asyncio.Event = asyncio.Event()
        self.sockets: Dict[int, Socket] = {}
        self.competitions: Dict[int, LeagueCompetition] = {}
        self.games: List[int] = []
        self.settings: GameSettings = GameSettings()
        self.account_manager: AccountManager = AccountManager(self)
        self.ticket_manager: TicketManager = TicketManager(self)
        self.jackpot_ready: bool = False
        self.game_map: List[int] = []
        self.game_map_lock: asyncio.Lock = asyncio.Lock()
        self.competition_align: bool = False
        self.sync_enabled: bool = True

    def online(self):
        if not self.active:
            self.active = True
            if not self.active_event.is_set():
                self.active_event.set()
            asyncio.ensure_future(self.read_user_data())
            self.install_competitions(self.games)
            self.ticket_manager.setup_jackpot()

    def offline(self):
        self.active = False
        if self.active_event.is_set():
            self.active_event.clear()

    def set_api_data(self, user_id: int, token: str, http: aiohttp.ClientSession):
        self.user_id = user_id
        self.token = token
        self.http = http

    # Resources
    def resource_tickets(self, details: Dict):
        return {
            'tagsId': None,
            'timeSend': get_ticket_timestamp(),
            'oddSettingsId': self.settings.odd_settings_id,
            'taxesSettingsId': self.settings.taxes_settings_id,
            'currency': self.settings.currency,
            'sellStaff': {
                'entityType': [{'val': "STAFF"}],
                'id': self.settings.unit_id,
                'name': self.settings.player_name,
                'lastName': None,
                'extId': "{}".format(self.settings.ext_id),
                'extData': None,
                'parentId': None,
                'enabled': None,
                'testMode': None,
                'hardwareId': None,
                'pinHash': None
            },
            'gameType': {
                'val': "ME"
            },
            'details': details,
        }

    @staticmethod
    def resource_find_ticket_by_id(details: Dict):
        ticket_id = details.get('ticket_id', None)
        data = {
            'n': details.get('n'),
            'filter': None,
        }
        if ticket_id:
            data.setdefault('ticketId', ticket_id)
        return data

    def get_ticket_by_id(self, n, ticket_id: int = None) -> Dict:
        options = dict()
        options.setdefault('ticket_id', ticket_id)
        options.setdefault('n', n)
        payload = self.resource_find_ticket_by_id(options)  # type: Dict
        return payload

    # Accounts
    async def setup_session(self, body: Dict):
        # Setup balance
        session_status = body.get('sessionStatus')  # type: Dict
        await self.process_session_status(session_status)
        # Game settings
        if not self.settings.configured:
            self.settings.configured = True
            self.settings.process_displays(body.get('displays'))
            self.settings.process_game_settings(body.get('gameSettings'))
            self.settings.process_auth(body.get('auth'))
            self.settings.process_localization(body.get('localization'))
            self.settings.taxes_settings_id = body.get('taxesSettings')
            self.settings.ext_data = body.get('extData')
            self.settings.odd_settings_id = body.get('oddSettingsId')

    async def process_session_status(self, session_status: Dict):
        credit = session_status.get('credit')  # type: float
        jackpot = session_status.get('jackpots')  # type: List
        user_jackpot = jackpot[0]  # type: Dict
        self.account_manager.bonus_level = user_jackpot.get('bonusLevel')
        self.account_manager.jackpot_amount = user_jackpot.get('amount')

        # Enable jackpot
        if self.account_manager.is_bonus_ready():
            if not self.jackpot_ready:
                self.jackpot_setup()
        else:
            if self.jackpot_ready:
                self.jackpot_reset()
        # update credit
        if not self.demo:
            if credit > 0:
                await self.account_manager.update(credit)

    def jackpot_setup(self):
        # Notify competitions of jackpot ready
        for a in self.competitions.values():
            a.setup_jackpot()

        self.jackpot_ready = True
        self.sync_enabled = False
        self.ticket_manager.buffer_tickets = False
        if self.ticket_manager.jackpot_resume == TicketManager.JACKPOT_NIL:
            self.ticket_manager.jackpot_resume = TicketManager.JACKPOT_AFTER
        else:
            self.ticket_manager.jackpot_resume = TicketManager.JACKPOT_BEFORE

        if self.ticket_manager.jackpot_resume == TicketManager.JACKPOT_AFTER:
            pass
            # self.ticket_manager.buffer_tickets = True
        logger.info(f'[{self.username}] Jackpot ready [{self.account_manager.jackpot_amount}] '
                    f'[{self.ticket_manager.jackpot_resume} : {self.ticket_manager.buffer_tickets}]')

    def jackpot_reset(self):
        # Notify competitions of jackpot ready
        for a in self.competitions.values():
            a.clear_jackpot()

        self.sync_enabled = True
        self.jackpot_ready = False
        self.ticket_manager.buffer_tickets = False
        self.ticket_manager.jackpot_resume = TicketManager.JACKPOT_NIL

    # Callbacks
    async def sync_callback(self, xs: int, valid_response: bool, body: Dict):
        if valid_response:
            session_status = body.get('sessionStatus', {})  # type: Dict
            if session_status:
                await self.process_session_status(session_status)

    async def ticket_callback(self, game_id: int, xs: int, valid_response: bool, body: Dict):
        ticket = await self.ticket_manager.find_ticket_by_xs(game_id, xs)  # type: Union[Ticket, None]
        if not ticket:
            print(f'{game_id}, {xs}, {valid_response}, {self.ticket_manager.socket_map}')
        else:
            pass
            # logger.debug(f'[{self.username}:{ticket.game_id}] {ticket.player} ticket response \n{ticket}')
        if ticket:
            transaction = body.get('transaction', None)  # type: Dict
            if transaction:
                # t = body.get('ticket')
                new_credit = transaction.get('newCredit')  # type: float
                self.account_manager.total_stake = ticket.stake
                await self.account_manager.update(new_credit)
                logger.debug(f'[{self.username}:{ticket.game_id}] {ticket.player} ticket success {ticket}')
                await self.ticket_manager.ticket_success(ticket)
            else:
                error_code = int(body.get('errorCode', None))
                message = body.get('message', None)
                logger.warning(f'[{self.username}:{ticket.game_id}] {ticket.player} '
                               f'ticket error Code: {error_code} Message: {message}')
                await self.ticket_manager.ticket_failed(error_code, ticket)

    @staticmethod
    async def tickets_find_by_id_callback(xs: int, valid_response: bool, body: Any):
        # TODO: Type checks
        if isinstance(body, list):
            ticket_ids = []
            if body:
                for ticket in body:
                    ticket_id = ticket.get('ticketId')
                    status = ticket.get('status')
                    won_data = ticket.get('wonData')
                    ticket_ids.append(ticket_id)
                    time_send = ticket.get('timeSend')
                    time_register = ticket.get('timeRegister')
                    server_hash = ticket.get('serverHash')
                    won_amount = 0
                    won_jackpot = 0
                    if won_data:
                        won_amount = won_data.get('wonAmount')
                        won_jackpot = won_data.get('wonJackpot')
                    # print(f'{ticket_id} {time_send} {time_register} {server_hash} {won_amount} {won_jackpot} {
                    # status}')

    # Sockets configuration
    async def socket_online(self, socket_id: int):
        competition = self.get_competition(socket_id)
        if competition:
            competition.online = True

    async def socket_lost(self, socket_id: int):
        competition = self.get_competition(socket_id)
        if competition:
            competition.lost = True

    async def socket_offline(self, socket_id: int):
        competition = self.get_competition(socket_id)
        if competition:
            competition.online = False
            for competition in self.competitions.values():
                if competition.online or competition.lost:
                    return
            await self.http.close()
            if not self.ticket_manager.sockets:
                self.close_event.set()
            else:
                self.ticket_manager.exit()

    # Tickets
    def register_ticket(self, ticket: Ticket):
        self.ticket_manager.register_ticket(ticket)

    def tickets_complete(self, game_id: int):
        competition = self.get_competition(game_id)
        if competition:
            asyncio.ensure_future(competition.on_ticket_complete())

    async def reset_competition_tickets(self, game_id: int):
        await self.ticket_manager.reset_competition_tickets(game_id)

    async def validate_competition_tickets(self, game_id: int):
        await self.ticket_manager.validate_competition_tickets(game_id)

    async def resolved_competition_ticket(self, ticket: Ticket):
        competition = self.get_competition(ticket.game_id)
        if competition:
            await competition.on_ticket_resolve(ticket)

    async def register_competition_ticket(self, ticket: Ticket):
        if self.competition_align:
            if ticket.registered:
                return
            async with self.game_map_lock:
                self.game_map.append(ticket.game_id)
                self.game_map = self.game_map[1:]
            await self.write_user_data()
            ticket.registered = True

    async def resume_competition(self, game_id: int) -> bool:
        return await self.ticket_manager.resume_competition_tickets(game_id)

    async def is_next_game_id(self, game_id: int) -> bool:
        async with self.game_map_lock:
            return game_id == self.game_map[0]

    # Api
    def get_competition(self, game_id: int) -> Optional[LeagueCompetition]:
        return self.competitions.get(game_id, None)  # type: Union[LeagueCompetition, None]

    def get_socket(self, socket_id: int) -> Optional[Socket]:
        return self.sockets.get(socket_id, None)  # type: Union[Socket, None]

    def create_competition(self, game_id: int) -> Tuple[bool, LeagueCompetition]:
        state = False
        competition = self.get_competition(game_id)
        if competition:
            pass
        else:
            state = True
            competition = LeagueCompetition(self, game_id)
            self.competitions[game_id] = competition
        return state, competition

    # TODO: Fix or remove api to integrate with player_uri
    def modify_player(self, player_name: str, odd_id: str, games: List):
        logger.info(f'[{self.username} Updating player configurations ')
        for game_id in games:
            competition = self.get_competition(game_id)
            if competition:
                competition.modify_player(player_name, odd_id)

    def install_competitions(self, competitions: List[int]):
        for competition_id in competitions:
            competition = self.get_competition(competition_id)
            if competition:
                continue
            else:
                state, competition = self.create_competition(competition_id)
                if state:
                    logger.debug(f'[{self.username}:{competition_id}] installing competition')
                    socket = self.get_socket(competition_id)
                    if not socket:
                        socket = Socket(self, competition_id)
                        self.sockets[competition_id] = socket
                        socket.connect()
                    competition.init()

    def send(self, socket_id: int, resource: str, body: Dict) -> int:
        socket = self.get_socket(socket_id)
        if socket:
            return socket.send(resource, body)
        return -1

    async def receive(self, socket_id: int, xs: int, resource: str, valid_response: bool, body: Dict):
        if resource == Resource.SYNC:
            await self.sync_callback(xs, valid_response, body)
        elif resource == Resource.TICKETS:
            await self.ticket_callback(socket_id, xs, valid_response, body)
        elif resource == Resource.TICKETS_FIND_BY_ID:
            await self.tickets_find_by_id_callback(xs, valid_response, body)
        else:
            competition = self.get_competition(socket_id)
            if competition:
                await competition.receive(xs, resource, body)

    def get_competition_results(self, game_id: int) -> Tuple[Dict, Dict]:
        competition = self.get_competition(game_id)
        if competition:
            return competition.get_ticket_validation_data()
        return {}, {}

    async def is_competition_online(self, game_id: int) -> bool:
        competition = self.get_competition(game_id)
        if competition:
            return competition.online
        return False

    async def read_user_data(self):
        try:
            async with aiofile.AIOFile(f'{settings.DATA_DIR}/{self.username}.json', 'r') as afp:
                body = decode_json(await afp.read())
                self.game_map = body.get('data', [])
        except FileNotFoundError as er:
            pass
        finally:
            game_map = set(settings.LIVE_GAMES)
            user_g = set(self.game_map)
            if game_map - user_g:
                self.game_map = list(game_map)
                await self.write_user_data()
            else:
                self.game_map = list(self.game_map)

    async def write_user_data(self):
        async with aiofile.AIOFile(f'{settings.DATA_DIR}/{self.username}.json', 'w') as afp:
            body = {'data': self.game_map}
            await afp.write(encode_json(body))

    async def store_competition(self, game_id: int, league: int,  data: Dict):
        event_loop = asyncio.get_event_loop()
        dump_data = await event_loop.run_in_executor(None, encode_json, data)
        async with aiofile.AIOFile(f'{settings.CACHE_DIR}/{game_id}/{self.username}_{league}.json', 'w') as afp:
            await afp.write(dump_data)
        logger.debug(f'[{self.username}:{game_id}] uploaded data  League: [{league}:{len(data)}]')

    async def exit(self):
        for competition_id, competition in self.competitions.items():
            asyncio.create_task(competition.exit())
        await self.close_event.wait()
