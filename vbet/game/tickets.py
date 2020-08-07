from vbet.utils.log import get_logger, async_exception_logger, exception_logger
from vbet.utils.parser import Resource
from vbet.core import settings
from vbet.game.socket import Socket, TICKET_SOCKET
from typing import List, Dict, Tuple
from operator import attrgetter
import asyncio
import time

logger = get_logger('ticket-manager')


class Bet:
    def __init__(
            self, odd_id: int, market_id: str, odd_value: float, odd_name: str,
            stake: float):
        self.odd_id = odd_id
        self.market_id = market_id
        self.odd_value = odd_value
        self.odd_name = odd_name
        self.stake = stake
        self.profit_type = "NONE"
        self.status = 'OPEN'

    def __str__(self):
        return "OddId: {} MarketId: {} OddName: {} OddValue: {} Stake {}".format(self.odd_id,
                                                                                 self.market_id, self.odd_name, self.odd_value, self.stake)


class Event:
    def __init__(self, event_id: int, league: int, week: int,
                 participants: List):
        self.event_id = event_id
        self.bets = []
        self.final_outcome = []
        self.game_type = "GL"
        self.playlist_id = None
        self.event_time = None
        self.ext_id = None
        self.is_banker = False
        # data
        self.league = league
        self.week = week
        self.event_ndx = None
        self.participants = participants

    @property
    def stake(self):
        _stake = 0
        for bet in self.bets:
            _stake += bet.stake
        return _stake

    def get_formatted_participants(self):
        players = []
        for player in self.participants:
            players.append(player.get('fifaCode'))
        return players

    @property
    def min_win(self):
        m = 0
        for bet in self.bets:
            odd = bet.odd_value
            stake = bet.stake
            m = round(odd * stake, 2)
        return m

    def __str__(self):
        bets = [bet.__str__() for bet in self.bets]
        bets_str = "\n".join(bets)
        return f'Event Id : {self.event_id} {self.get_formatted_participants()} \n{bets_str}'

    def add_bet(self, bet: Bet):
        self.bets.append(bet)


class Ticket:
    SINGLE = 'SINGLE'
    MULTIPLE = 'MULTIPLE'

    READY = 0
    WAITING = 1
    SENT = 2
    FAILED = 3
    SUCCESS = 4
    VOID = -1
    ERROR_CREDIT = 5
    NETWORK = 6

    def __init__(self, game_id: int, player: str):
        self.xs: int = -1
        self.game_id = game_id
        self.ticket_key = None
        self.player = player
        self.content = None
        self.events = []
        self.settings = {}
        self.priority = 0
        self.sent: bool = False
        self.socket_id = None
        self._min_winning = 0
        self._max_winning = 0
        self._total_won = 0
        self._status: int = self.READY
        self._grouping = 0
        self._system_count = 0
        self._winning_count = 0
        self._stake = 0
        self.resolved = False
        self.registered = False
        self._sent_time: float = 0

    def __str__(self):
        events = [event.__str__() for event in self.events]
        events_str = "\n".join(events)
        return f'Ticket : {self.mode} State : {self.status} Stake : {self.stake} \n{events_str}'

    def set_priority(self, priority: int):
        self.priority = priority

    def is_valid(self):
        if self.events:
            return True
        return False

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        self._status = status

    @property
    def mode(self):
        if len(self.events) == 1:
            return Ticket.SINGLE
        return Ticket.MULTIPLE

    @property
    def sent_time(self):
        return self._sent_time

    def sent_notify(self, xs, socket_id):
        self.xs = xs
        self.socket_id = socket_id
        self._sent_time = time.time()

    @property
    def stake(self):
        return self._stake

    @stake.setter
    def stake(self, stake: float):
        self._stake = round(stake, 2)

    @property
    def total_won(self):
        return self._total_won

    @total_won.setter
    def total_won(self, amount: float):
        self._total_won = amount

    @property
    def grouping(self):
        return self._grouping

    @grouping.setter
    def grouping(self, grouping: int):
        self._grouping = grouping

    @property
    def system_count(self):
        return self._system_count

    @system_count.setter
    def system_count(self, count: int):
        self._system_count = count

    @property
    def winning_count(self):
        return self._winning_count

    @winning_count.setter
    def winning_count(self, count: int):
        self._winning_count = count

    @property
    def min_winning(self):
        return self._min_winning

    @min_winning.setter
    def min_winning(self, winning: float):
        self._min_winning = winning

    @property
    def max_winning(self):
        return self._max_winning

    @max_winning.setter
    def max_winning(self, winning: float):
        self._max_winning = winning

    @property
    def system_bets(self):
        return [{
            'grouping': self.grouping,
            'systemCount': self.system_count,
            'stake': self.stake,
            'winningData': {
                'limitMaxPayout': 200000,
                'minWinning': self.min_winning,
                'maxWinning': self.min_winning,
                'minBonus': 0,
                'maxBonus': 0,
                'winningCount': self.winning_count
            }
        }]

    def add_event(self, event: Event):
        self.events.append(event)

    def resolve(self, results: Dict):
        if self.mode == Ticket.SINGLE:
            for event in self.events:
                event_data = results.get(event.event_id)
                won_data = event_data[0]
                winnings = event_data[1]
                refund_stake = winnings.get('refund_stake')
                half_lost = winnings.get('half_lost')
                half_won = winnings.get('half_won')
                for bet in event.bets:
                    if str(bet.odd_id) in refund_stake:
                        self._total_won += bet.stake
                    elif str(bet.odd_id) in half_lost:
                        self._total_won += (bet.stake / 2)
                    elif str(bet.odd_id) in half_won:
                        self._total_won += round((bet.stake / 2) * bet.odd_value, 2)
                    elif bet.odd_id in won_data:
                        won = round(bet.stake * bet.odd_value, 2)
                        self._total_won += won
                break
        else:
            if self.winning_count >= 1 and self.grouping == 1:
                for event in self.events:
                    for bet in event.bets:
                        if bet.odd_id in results[event.event_id]:
                            self._total_won += round(bet.stake * bet.odd_value, 2)
            if self.winning_count == 1 and self.grouping > 1:
                total_odd = 1
                for event in self.events:
                    for bet in event.bets:
                        if bet.odd_id in results[event.event_id]:
                            total_odd *= bet.odd_value
                        else:
                            return self._total_won
                self._total_won = total_odd * self.stake
        return self._total_won

    def can_resolve(self, results: Dict, winning_ids: Dict) -> Dict:
        required_results = {}
        for event in self.events:
            week_result = results.get(event.week, {})
            week_winnings = winning_ids.get(event.week, {})
            if not week_result:
                return {}
            event_data = week_result.get(event.event_id, [])
            event_winnings = week_winnings.get(event.event_id, {})
            if not event_data:
                return {}
            required_results[event.event_id] = [event_data, event_winnings]
        return required_results


class TicketManager:
    DEFAULT_TICKET_INTERVAL = 2
    JACKPOT_BEFORE = 0
    JACKPOT_AFTER = 1
    JACKPOT_NIL = 2

    def __init__(self, user):
        self.user = user
        self.ticket_queue = asyncio.Queue()
        self._ticket_key = 0
        self._ticket_id_lock = asyncio.Lock()
        self.active_tickets: Dict[int, Dict[int, Ticket]] = {}
        self.ticket_interval = self.DEFAULT_TICKET_INTERVAL
        self.demo_ticket_interval = 2
        self.last_ticket_time = time.time()
        self.buffer_tickets = False  # Await response of last ticket before sending next
        self.ticket_lock = asyncio.Lock()
        self.send_lock = asyncio.Lock()
        self.reg_lock = asyncio.Lock()
        self.pool_lock = asyncio.Lock()
        self.ticket_sender_future: asyncio.Future = asyncio.create_task(self.ticket_listener())
        self.ticket_scanner_future: asyncio.Future = asyncio.create_task(self.ticket_scanner())
        self._ticket_wait = asyncio.Event()
        self.sockets: Dict[int, Socket] = {}
        self.socket_map: Dict[int, Dict[int, int]] = {}
        self.min_sockets = 2
        self.jackpot_resume: int = self.JACKPOT_NIL
        self.host_index = -1

    async def ticket_scanner(self):
        logger.debug(f'[{self.user.username}] ticket scanner started')
        while True:
            to_remove = []
            for game_id, competition_tickets in self.active_tickets.items():
                for ticket_key, ticket in competition_tickets.items():
                    if ticket.status == Ticket.ERROR_CREDIT:
                        credit = await self.user.account_manager.credit
                        if credit > ticket.stake:
                            ticket.status = Ticket.READY
                            logger.info(f'Ticket Resume [{credit} : {ticket.stake}]')
                        else:
                            logger.warning(f'Ticket Check [{credit} : {ticket.stake}]')
                    if ticket.status == Ticket.VOID:
                        to_remove.append(ticket)
                    if ticket.status == Ticket.SENT:
                        age = ticket.sent_time
                        now = time.time()
                        # if now - age > 20:
                        #     ticket.status = Ticket.READY
                        #      # print(f"Out of time ticket {ticket.events}")
                    if ticket.status == Ticket.SUCCESS and ticket.resolved:
                        to_remove.append(ticket)

            for t in to_remove:
                await self.remove_ticket(t)
            await self.poll_ticket()
            await asyncio.sleep(1)

    async def ticket_listener(self):
        logger.debug(f'[{self.user.username}] queue listener started')
        while True:
            await self.poll_ticket()
            await self.wait_ticket_interval()
            ticket_data = await self.ticket_queue.get()
            game_id, ticket_key = ticket_data[0], ticket_data[1]
            ticket = await self.find_ticket(game_id, ticket_key)
            if ticket is not None:
                if self.user.account_manager.is_bonus_ready():
                    if not self.user.jackpot_ready:
                        self.user.jackpot_setup()
                else:
                    if self.user.jackpot_ready:
                        self.user.jackpot_reset()
                await self.send_ticket(ticket)
            else:
                break

        logger.debug(f'[{self.user.username}] queue listener stopped')

    def register_ticket(self, ticket: Ticket):
        ticket_key = self.generate_ticket_key()
        ticket.ticket_key = ticket_key
        return ticket_key

    async def send_ticket(self, ticket: Ticket):
        async with self.send_lock:
            if self.buffer_tickets:
                await self.ticket_lock.acquire()
            if self.user.demo:
                await self.resolve_demo_ticket(ticket)
            else:
                credit = await self.user.account_manager.credit
                if credit >= ticket.stake:
                    logger.debug(f'[{self.user.username}:{ticket.game_id}] [{ticket.player}] stake : {ticket.stake}')
                    await self.resolve_ticket(ticket)
                else:
                    ticket.status = Ticket.ERROR_CREDIT
                    logger.warning(f'[{self.user.username}:{ticket.game_id}] [{ticket.player}] error-credit '
                                   f'[{ticket.stake}]')
                    self.last_ticket_time = time.time() - self.ticket_interval  # No ticket sent so can send instant

    async def resolve_ticket(self, ticket: Ticket):
        ticket_data = self.user.resource_tickets(ticket.content)
        socket = await self.get_available_socket()
        while True:
            if not socket:
                self._ticket_wait.clear()
                await self._ticket_wait.wait()
                socket = await self.get_available_socket()
            else:
                break
        xs = socket.send(Resource.TICKETS, body=ticket_data)
        ticket.status = Ticket.SENT
        ticket.sent_notify(xs, socket.socket_id)
        socket_map = self.socket_map.get(socket.socket_id, {})
        socket_map[ticket.xs] = ticket.game_id
        self.socket_map[socket.socket_id] = socket_map
        if not self.user.jackpot_ready:
            await socket.sync()

    async def resolve_demo_ticket(self, ticket: Ticket):
        status, amount = await self.user.account_manager.borrow(ticket.stake)
        if status:
            ticket.status = Ticket.SUCCESS
            await self.user.register_competition_ticket(ticket)
            await self.poll_ticket()
            logger.debug(f'[{self.user.username}:{ticket.game_id}] [{ticket.player}] simulation stake : '
                         f'[{ticket.stake}]')
            self.user.account_manager.total_stake = ticket.stake
        else:
            logger.debug(f'[{self.user.username}:{ticket.game_id}] [{ticket.player}] out_of_credit')

        await self.check_pending_tickets(ticket.game_id)

    async def ticket_success(self, ticket: Ticket):
        ticket.status = Ticket.SUCCESS
        await self.user.register_competition_ticket(ticket)
        await self.poll_ticket()
        if self.buffer_tickets:
            if self.ticket_lock.locked():
                self.ticket_lock.release()
        await self.check_pending_tickets(ticket.game_id)

    async def ticket_failed(self, error_code: int, ticket: Ticket):
        # Assign error code
        if error_code == 602:
            ticket.status = Ticket.VOID
        elif error_code == 603:
            ticket.status = Ticket.VOID
        elif error_code == 605:
            ticket.status = Ticket.ERROR_CREDIT
        else:
            ticket.status = Ticket.FAILED

        # Retry sending
        if error_code in [604, 500]:
            await self.poll_ticket()

        if self.buffer_tickets:
            if self.ticket_lock.locked():
                self.ticket_lock.release()

        # Invalid block to place ticket
        if error_code == 602:
            await self.check_pending_tickets(ticket.game_id)

        if error_code == 603:
            await self.poll_ticket()

    async def poll_ticket(self):
        for game_id, competition_tickets in self.active_tickets.items():
            for ticket_key, t in competition_tickets.items():
                if t.status == Ticket.READY or t.status == Ticket.FAILED:
                    if self.user.competition_align:
                        if await self.user.is_next_game_id(t.game_id):
                            if self.ticket_queue.qsize() < 50:
                                await self.ticket_queue.put((t.game_id, t.ticket_key))
                                t.status = Ticket.WAITING
                    else:
                        if self.ticket_queue.qsize() < 50:
                            await self.ticket_queue.put((t.game_id, t.ticket_key))
                            t.status = Ticket.WAITING

    async def add_ticket(self, ticket: Ticket):
        async with self.pool_lock:
            competition_tickets = self.active_tickets.get(ticket.game_id, {})
            competition_tickets[ticket.ticket_key] = ticket
            self.active_tickets[ticket.game_id] = competition_tickets

    async def remove_ticket(self, ticket: Ticket):
        async with self.pool_lock:
            competition_tickets = self.active_tickets.get(ticket.game_id, {})
            if competition_tickets:
                try:
                    competition_tickets.pop(ticket.ticket_key)
                except KeyError:
                    pass
            self.active_tickets[ticket.game_id] = competition_tickets

    async def find_ticket(self, game_id: int, ticket_key: int):
        async with self.pool_lock:
            competition_tickets = self.active_tickets.get(game_id, {})
            if competition_tickets:
                ticket = competition_tickets.get(ticket_key, None)
                return ticket

    async def find_ticket_by_xs(self, socket_id, xs: int):
        async with self.send_lock:
            socket_map = self.socket_map.get(socket_id, {})
            try:
                game_id = socket_map.pop(xs)
                if socket_map:
                    self.socket_map[socket_id] = socket_map
                else:
                    self.socket_map.pop(socket_id)
            except KeyError:
                pass
            else:
                if not self._ticket_wait.is_set():
                    self._ticket_wait.set()
                competition_tickets = self.active_tickets.get(game_id, {})
                for ticket_key, ticket in competition_tickets.items():
                    if ticket.xs == xs and ticket.socket_id == socket_id:
                        return ticket

    async def check_pending_tickets(self, game_id: int):
        competition_tickets = self.active_tickets.get(game_id)
        for ticket_key, ticket in competition_tickets.items():
            if ticket.status != Ticket.SUCCESS and ticket.status != Ticket.VOID:
                return True
        self.user.tickets_complete(game_id)

    async def resume_competition_tickets(self, game_id: int):
        competition_tickets = self.active_tickets.get(game_id)
        a = False
        for ticket_key, ticket in competition_tickets.items():
            if ticket.status == Ticket.READY or ticket.status == Ticket.WAITING or ticket.status == Ticket.FAILED:
                a = True
        return a

    async def reset_competition_tickets(self, game_id: int):
        competition_tickets = self.active_tickets.get(game_id, {})
        for ticket_key, ticket in competition_tickets.items():
            ticket.status = Ticket.VOID
        self.active_tickets[game_id] = {}

    async def validate_competition_tickets(self, game_id: int):
        competition_tickets = self.active_tickets.get(game_id, {})
        if competition_tickets:
            results, winning_ids = self.user.get_competition_results(game_id)
            for ticket in competition_tickets.values():
                if ticket.status == Ticket.SUCCESS and not ticket.resolved:
                    validation_data = ticket.can_resolve(results, winning_ids)
                    if validation_data:
                        ticket.resolve(validation_data)
                        ticket.resolved = True
                        await self.user.resolved_competition_ticket(ticket)
                        credit = await self.user.account_manager.credit
                        bonus_level = self.user.account_manager.bonus_level
                        jackpot_val = self.user.account_manager.jackpot_value
                        jackpot_amount = self.user.account_manager.jackpot_amount
                        total_stake = self.user.account_manager.total_stake

                        credit_str = f'{credit:.2f}'
                        credit_str = credit_str.ljust(9)
                        jackpot_val_str = f'{jackpot_val:.2f}%'
                        jackpot_val_str = jackpot_val_str.ljust(6)
                        jackpot_amount_str = f'{jackpot_amount:.2f}'
                        jackpot_amount_str = jackpot_amount_str.ljust(7)
                        bonus_level_str = f'L{bonus_level + 1}'
                        account_str = f'[Ksh : {credit_str}] [{bonus_level_str} : {jackpot_val_str} : {jackpot_amount_str}]'
                        stake_str = f'{ticket.stake:.2f}'
                        stake_str = stake_str.ljust(9)
                        won_str = f'{ticket.total_won:.2f}'
                        won_str = won_str.ljust(9)
                        total_stake_str = f'{total_stake:.2f}'
                        total_stake_str = total_stake_str.ljust(9)
                        bet_str = f'[stake : {stake_str} won : {won_str} total : {total_stake_str}]'
                        logger.info(f'[{self.user.username}:{game_id}] {ticket.player} {account_str} {bet_str}')

    async def wait_ticket_interval(self):
        if self.user.jackpot_ready:
            self.last_ticket_time = time.time()
            return
        else:
            ticket_interval = self.demo_ticket_interval if self.user.demo else self.ticket_interval
        now = time.time()
        gap = now - self.last_ticket_time
        if ticket_interval > 0:
            to_sleep = ticket_interval - gap
            if to_sleep > 0:
                await asyncio.sleep(to_sleep)
        self.last_ticket_time = time.time()

    async def get_available_socket(self):
        sockets = [socket for socket in self.sockets.values() if socket.authorized]
        if sockets:
            socket = sorted(sockets, key=attrgetter('last_used'))[0]
            socket.last_used = time.time()
            return socket

    def setup_jackpot(self):
        for i in range(0, self.min_sockets):
            socket = Socket(self.user, i, mode=TICKET_SOCKET)
            self.sockets[i] = socket
            socket.connect()

    def close_sockets(self):
        for socket in self.sockets.values():
            future = asyncio.create_task(socket.exit())

    def generate_ticket_key(self):
        self._ticket_key += 1
        return self._ticket_key

    def get_server_host(self):
        self.host_index += 1
        if self.host_index >= len(settings.SERVERS):
            self.host_index = 0
        return settings.SERVERS[self.host_index]

    def exit(self):
        self.close_sockets()
        self.ticket_scanner_future.cancel()
        self.ticket_sender_future.cancel()
