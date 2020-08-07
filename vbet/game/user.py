from vbet.utils.log import *
from vbet.core import settings
from vbet.game.socket import Socket
import asyncio
import aiohttp
from typing import Dict, List, Union, Any
from .competition import *
from .accounts import AccountManager
from .tickets import Ticket, Event, Bet, TicketManager
from vbet.utils.parser import Resource, encode_json, decode_json, get_ticket_timestamp
import queue
import random
import aiofile

logger = get_logger('user')


class GameSettings:
    def __init__(self):
        self._odd_settings_id: int = 0
        self._playlists: Dict[int, Dict] = {}
        self._taxes_settings = {}
        self._game_settings = {}
        self._unit_id = None
        self._ext_id = None
        self._ext_data = None
        self._player_name = None
        self._currency: Dict = {}
        self.configured = False

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
    def __init__(self, username: str, is_demo: bool, manager):
        self.username = username
        self.manager = manager
        self._demo = is_demo
        self.http: aiohttp.ClientSession = None
        self.token: str = None
        self.user_id: int = None
        self.active = False
        self.active_event = asyncio.Event()
        self.close_event = asyncio.Event()
        self.sockets: Dict[int, Socket] = {}
        self.competitions: Dict[int, LeagueCompetition] = {}
        self.games: List[int] = []
        self.settings = GameSettings()
        self.account_manager = AccountManager(self)
        self.ticket_manager = TicketManager(self)
        self.jackpot_ready = False
        self.game_map = []
        self.game_map_lock = asyncio.Lock()
        self.competition_align = False
        self.sync_enabled = True

    @property
    def demo(self):
        return self._demo

    @demo.setter
    def demo(self, is_demo: bool):
        self._demo = is_demo

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

    def resource_find_ticket_by_id(self, details: Dict):
        ticket_id = details.get('ticket_id', None)
        data = {
            'n': details.get('n'),
            'filter': None,
        }
        if ticket_id:
            data.setdefault('ticketId', ticket_id)
        return data

    def get_ticket_by_id(self, n, ticket_id: int = None):
        options = dict()
        options.setdefault('ticket_id', ticket_id)
        options.setdefault('n', n)
        payload = self.resource_find_ticket_by_id(options)
        return payload

    # Accounts
    async def setup_session(self, body: Dict):
        # Setup balance
        session_status = body.get('sessionStatus')
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
        credit = session_status.get('credit')
        jackpot = session_status.get('jackpots')
        user_jackpot = jackpot[0]
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
            session_status = body.get('sessionStatus')
            await self.process_session_status(session_status)

    async def ticket_callback(self, game_id: int, xs: int, valid_response: bool, body: Dict):
        ticket = await self.ticket_manager.find_ticket_by_xs(game_id, xs)
        if not ticket:
            print(f'{game_id}, {xs}, {valid_response}, {self.ticket_manager.socket_map}')
        else:
            pass
            # logger.debug(f'[{self.username}:{ticket.game_id}] {ticket.player} ticket response \n{ticket}')
        if ticket:
            transaction = body.get('transaction')
            if transaction:
                # t = body.get('ticket')
                new_credit = transaction.get('newCredit')
                self.account_manager.total_stake = ticket.stake
                await self.account_manager.update(new_credit)
                logger.debug(f'[{self.username}:{ticket.game_id}] {ticket.player} ticket success {ticket}')
                await self.ticket_manager.ticket_success(ticket)
            else:
                error_code = int(body.get('errorCode'))
                message = body.get('message')
                logger.warning(f'[{self.username}:{ticket.game_id}] {ticket.player} '
                               f'ticket error Code: {error_code} Message: {message}')
                await self.ticket_manager.ticket_failed(error_code, ticket)

    async def tickets_find_by_id_callback(self, xs: int, valid_response: bool, body: Any):
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
                    print(f'{ticket_id} {time_send} {time_register} {server_hash} {won_amount} {won_jackpot} {status}')
            print("\n")
        else:
            print(body)

    # Sockets configuration
    async def socket_online(self, socket_id: int):
        competition = self.competitions.get(socket_id, None)
        if competition:
            competition.online = True

    async def socket_lost(self, socket_id: int):
        competition = self.competitions.get(socket_id, None)
        if competition:
            competition.lost = True

    async def socket_offline(self, socket_id: int):
        competition = self.competitions.get(socket_id, None)
        if competition:
            competition.online = False
            for competition in self.competitions.values():
                if competition.online or competition.lost:
                    return
            await self.http.close()
            self.ticket_manager.exit()
        else:
            socket = self.ticket_manager.sockets.get(socket_id)
            if socket:
                self.ticket_manager.sockets.pop(socket_id)
            if not self.ticket_manager.sockets:
                self.close_event.set()

    # Tickets
    def register_ticket(self, ticket: Ticket):
        self.ticket_manager.register_ticket(ticket)

    def tickets_complete(self, game_id: int):
        competition = self.get_competition(game_id)
        asyncio.ensure_future(competition.on_ticket_complete())

    async def reset_competition_tickets(self, game_id: int):
        await self.ticket_manager.reset_competition_tickets(game_id)

    async def validate_competition_tickets(self, game_id: int):
        await self.ticket_manager.validate_competition_tickets(game_id)

    async def resolved_competition_ticket(self, ticket: Ticket):
        competition = self.get_competition(ticket.game_id)
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

    async def resume_competition(self, game_id: int):
        await self.ticket_manager.resume_competition_tickets(game_id)

    async def is_next_game_id(self, game_id: int):
        async with self.game_map_lock:
            return game_id == self.game_map[0]

    # Api
    def get_competition(self, game_id: int):
        return self.competitions.get(game_id, None)

    def get_socket(self, socket_id: int):
        return self.sockets.get(socket_id, None)

    def create_competition(self, game_id: int):
        state = False
        competition = self.competitions.get(game_id, None)
        if competition:
            pass
        else:
            state = True
            competition = LeagueCompetition(self, game_id)
            self.competitions[game_id] = competition
        return state, competition

    def modify_player(self, player_name: str, odd_id: str, games: List):
        logger.info(f'[{self.username} Updating player configurations ')
        for game_id in games:
            competition = self.get_competition(game_id)
            if competition:
                competition.modify_player(player_name, odd_id)

    def install_competitions(self, competitions: List[int]):
        for competition_id in competitions:
            competition = self.competitions.get(competition_id, None)
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

    def send(self, socket_id: int, resource: str, body: Dict):
        socket = self.get_socket(socket_id)
        return socket.send(resource, body)

    async def receive(self, socket_id: int, xs: int, resource: str, valid_response: bool, body: Dict):
        if resource == Resource.SYNC:
            await self.sync_callback(xs, valid_response, body)
        elif resource == Resource.TICKETS:
            await self.ticket_callback(socket_id, xs, valid_response, body)
        elif resource == Resource.TICKETS_FIND_BY_ID:
            await self.tickets_find_by_id_callback(xs, valid_response, body)
        else:
            competition = self.competitions.get(socket_id, None)
            if competition:
                await competition.receive(xs, resource, body)

    def get_competition_results(self, game_id: int) -> Tuple[Dict, Dict]:
        competition = self.get_competition(game_id)
        return competition.get_ticket_validation_data()

    async def is_competition_online(self, game_id: int):
        competition = self.get_competition(game_id)
        return competition.online

    async def read_user_data(self):
        try:
            async with aiofile.AIOFile(f'{settings.DATA_DIR}/{self.username}.json', 'r') as afp:
                body = decode_json(await afp.read())
                self.game_map = body.get('data', [])
        except FileNotFoundError as er:
            pass
        finally:
            game_map = {ITALY, LALIGA, PREMIER, GERMANY, KENYAN}
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
