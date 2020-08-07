from vbet.utils.log import get_logger, async_exception_logger, exception_logger
from datetime import datetime, timezone
import pytz
from typing import Dict, Any, List, Union, Tuple
from vbet.utils import exceptions
from vbet.utils.parser import map_resource_to_name
import asyncio
from vbet.utils.parser import Resource
import time

from abc import abstractmethod
from .markets import Markets
from .tickets import Ticket
from .table import LeagueTable
from vbet.game.players import Player, Messi, Ronaldo, Neymar, Arthur, Fati, Salah
import secrets


logger = get_logger('competition')
account_logger = get_logger('account')

GERMANY = 41047
LALIGA = 14036
PREMIER = 14045
ITALY = 14035
KENYAN = 14050
COMPETITIONS = [ITALY, LALIGA, PREMIER, GERMANY, KENYAN]


class LeagueCompetition:
    SCHEDULED = 0

    SLEEPING = 0
    EVENTS = 1
    TICKETS = 2
    RESULTS = 3

    def __init__(self, user, game_id: int):
        self.user = user
        self.game_id = game_id
        self.countdown: float = None
        self.offset: float = None
        self.mode: float = None
        if self.game_id == 41047 or self.game_id == 14050:
            self.max_week = 34
        else:
            self.max_week = 38
        self.event_time = None
        self.e_block_id = None
        self.league = None
        self.week = None
        self.table = LeagueTable(self.max_week)
        self.caching = False
        self.caching_future = False
        self.cache_enabled = True
        self.cached = False
        self.caching_multiple = False
        self.caching_single = False
        self.future_results = True
        self.fetching_future = False
        self.auto_skip = False

        self._online = False
        self.lost = False
        self.restoring = False
        self.phase = LeagueCompetition.SLEEPING

        self.required_weeks: List[int] = []
        self.history_count = 0
        self.max_history_count = 5
        self.event_time_enabled = True
        self.event_time_interval = 0
        self.profile = 'MOBILE'
        self.event_xs: Dict[int, Dict] = {}
        self.result_xs: Dict[int, Dict] = {}
        self.history_xs: Dict[int, Dict] = {}
        self.stats_xs: Dict[int, Dict] = {}
        self.result_event = asyncio.Event()
        self.team_labels: Dict[int, str] = {}
        self.active_tickets: List[int] = []
        self.blocks: Dict[int, int] = {}
        self.league_games: Dict[int, Dict] = {}
        self.socket_closed = False
        self.jackpot_ready = False

        self.players = {
            'messi': Messi(self),
            # 'salah': Salah(self),
            # 'neymar': Neymar(self),
            # 'arthur': Arthur(self),
            # 'fati': Fati(self),
            # 'ronaldo': Ronaldo(self)
        }

    def init(self):
        logger.info(f'[{self.user.username}:{self.game_id}] competition installed')

    def configure(self, game_config: Dict):
        self.countdown = game_config.get('countdown')
        self.offset = game_config.get('offset')
        self.mode = 1 if self.countdown > 0 else 0

    async def start(self):
        if self.lost:
            self.lost = False
            self.restoring = True
        await self.next_block_event()

    @property
    def online(self):
        return self._online

    @online.setter
    def online(self, online: bool):
        if online:
            if not self._online or self.lost:
                asyncio.ensure_future(self.start())
        self._online = online

    @property
    def authorized(self):
        return self._authorized

    @authorized.setter
    def authorized(self, status: bool):
        self._authorized = status

    def resource_events(self, options: Dict):
        event_time = self.get_event_time() if self.mode == self.SCHEDULED else None
        countdown = self.countdown if self.mode == self.SCHEDULED else None
        offset = self.offset if self.mode == self.SCHEDULED else None
        return {
            'contentType': "PLAYLIST",
            'contentId': self.game_id,
            'countDown': countdown,
            'offset': offset,
            'eventTime': event_time,
            'n': options.get('n'),
            'profile': self.profile,
            'oddSettingId': self.user.settings.odd_settings_id,
            'unitId': self.user.settings.unit_id
        }

    def resource_results(self, options: Dict):
        countdown = self.countdown if self.mode == self.SCHEDULED else None
        offset = self.offset if self.mode == self.SCHEDULED else None
        data = {
            'contentType': "PLAYLIST",
            'contentId': self.game_id,
            'countDown': countdown,
            'offset': offset,
            'profile': self.profile,
            'oddSettingId': self.user.settings.odd_settings_id,
            'unitId': self.user.settings.unit_id
        }
        if self.mode == self.SCHEDULED:
            event_time = self.event_time
        else:
            event_time = None
            data.setdefault('eBlockId', options.get('e_block_id'))
        data.setdefault('n', options.get('n'))
        data.setdefault('eventTime', event_time)
        return data

    def resource_stats(self, options: Dict):
        event_time = self.get_event_time() if self.mode == self.SCHEDULED else None
        countdown = self.countdown if self.mode == self.SCHEDULED else None
        offset = self.offset if self.mode == self.SCHEDULED else None
        return {
            'contentType': "PLAYLIST",
            'contentId': self.game_id,
            'countDown': countdown,
            'offset': offset,
            'eBlockId': options.get('e_block_id'),
            'eventTime': event_time,
            'n': options.get('n'),
            'profile': self.profile,
            'oddSettingId': self.user.settings.odd_settings_id,
            'unitId': self.user.settings.unit_id
        }

    def resource_history(self, options: Dict):
        return {
            'contentType': "PLAYLIST",
            'contentId': self.game_id,
            'countDown': None,
            'offset': None,
            'n': options.get('n'),
            'eBlockId': options.get('e_block_id'),
            'profile': self.profile,
            'oddSettingId': self.user.settings.odd_settings_id,
            'unitId': self.user.settings.unit_id
        }

    async def next_event(self, n: int):
        options = dict()
        options.setdefault('n', n)
        payload = self.resource_events(options)
        xs = self.send(Resource.EVENTS, payload)
        self.event_xs[xs] = payload

    async def next_result(self, e_block_id: int, n: int, retry_count: int = 0):
        options = dict()
        options.setdefault('e_block_id', e_block_id)
        options.setdefault('n', n)
        payload = self.resource_results(options)
        xs = self.send(Resource.RESULTS, payload)
        self.result_xs[xs] = {'payload': payload, 'retry_count': retry_count}

    async def next_history(self, e_block_id: int, n: int, retry_count: int = 0):
        options = dict()
        options.setdefault('e_block_id', e_block_id)
        options.setdefault('n', n)
        payload = self.resource_history(options)
        xs = self.send(Resource.HISTORY, payload)
        self.history_xs[xs] = {'payload': payload, 'retry_count': retry_count}

    async def next_stats(self, e_block_id: int, n: int):
        options = dict()
        options.setdefault('e_block_id', e_block_id)
        options.setdefault('n', n)
        payload = self.resource_stats(options)
        xs = self.send(Resource.STATS, payload)
        self.stats_xs[xs] = payload

    async def next_block_result(self, block: int = 1):
        await self.await_event_time()
        await self.next_result(self.e_block_id, block)

    async def next_block_event(self, block: int = 1):
        await self.next_event(block)

    async def next_block_future(self, e_block_id: int, block: int = 10):
        await self.next_history(e_block_id, block)

    @async_exception_logger('events')
    async def events_callback(self, xs: int, valid_response: bool, body: Any):
        options = self.event_xs.pop(xs)
        try:
            if valid_response and isinstance(body, list):
                try:
                    data = body[0]
                    if not isinstance(data, dict):
                        raise exceptions.InvalidEvents()
                except IndexError:
                    raise exceptions.InvalidEvents()
                else:
                    if self.restoring:
                        await self.resource_events_process_resume(data)
                    else:
                        await self.resource_events_process(data)
            else:
                raise exceptions.InvalidEvents()
        except exceptions.InvalidEvents:
            logger.warning(f'[{self.user.username}:{self.game_id}] Invalid events response')
            await asyncio.sleep(2)
            await self.next_event(options.get('n'))

    @async_exception_logger('results')
    async def results_callback(self, xs: int, valid_response: bool, body: Any):
        options: Dict = self.result_xs.pop(xs)
        payload = options.get('payload')
        retry_count = options.get('retry_count')
        e_block = payload.get('eBlockId')
        n = payload.get('n')
        try:
            if valid_response and isinstance(body, list):
                try:
                    data = body[0]
                    if not isinstance(data, dict):
                        raise ValueError
                except (ValueError, IndexError):
                    raise exceptions.InvalidResults(e_block, n, retry_count)
                else:
                    await self.resource_result_process(data)
            else:
                raise exceptions.InvalidResults(e_block, n, retry_count)
        except exceptions.InvalidResults as err:
            logger.warning(f'[{self.user.username}:{self.game_id}] Invalid results response Block: [{err.e_block_id} '
                           f':{err.n}] League: {self.league}'
                           f' Retry: {err.retry_count}')
            if retry_count > 3:
                self.auto_skip = True
                await self.next_block_event()
            else:
                await asyncio.sleep(3)
                await self.next_result(err.e_block_id, err.n, err.retry_count + 1)

    @async_exception_logger('history')
    async def history_callback(self, xs: int, valid_response: bool, body: Any):
        if self.history_count > self.max_history_count:
            self.auto_skip = True
            await self.next_block_event()
        options: Dict = self.history_xs.pop(xs)
        payload = options.get('payload')
        retry_count = options.get('retry_count')
        e_block = payload.get('eBlockId')
        n = payload.get('n')
        try:
            if valid_response and isinstance(body, list):
                await self.resource_history_process(e_block, n, body)
            else:
                raise exceptions.InvalidHistory(e_block, n, retry_count)

        except exceptions.InvalidHistory as err:
            logger.warning(f'[{self.user.username}:{self.game_id}] Invalid history response Block: [{err.e_block_id} '
                           f':{err.n}] League: {self.league}'
                           f' Retry: {err.retry_count}')
            if retry_count > 3:
                self.auto_skip = True
                await self.next_block_event()
            else:
                await asyncio.sleep(3)
                await self.next_history(err.e_block_id, err.n, err.retry_count + 1)

    async def resource_history_process(self, e_block: int, n: int, data: List[Dict]):
        e_blocks = []
        for week_result in data:
            events = week_result.get('events')
            e_block_id = week_result.get('eBlockId')
            e_blocks.append(e_block)
            event_data = week_result.get('data')
            league = event_data.get('leagueId')
            week = event_data.get('matchDay')
            if league != self.league:
                continue
            logger.debug(f'[{self.user.username}:{self.game_id}] History Block: {e_block_id} League: {league} Week:'
                         f' {week}')
            self.blocks[e_block_id] = week
            results = {}
            matches = {}
            winning_ids = {}
            result_ids = {}
            for event_index, event in enumerate(events):
                data = event.get('data')
                participants = data.get('participants')
                player_a = participants[0]
                player_b = participants[1]
                team_a = player_a.get('fifaCode')
                team_b = player_b.get('fifaCode')
                event_id = event.get('eventId')
                result = event.get('result')
                odds = []  # type: List[float]
                odd_values = data.get('oddValues')  # type: List[str]
                for odd in odd_values:
                    odds.append(float(odd))
                matches[event_id] = {'A': team_a, 'B': team_b, 'odds': odds, 'index': event_index, 'participants':
                    participants}
                if self.caching:
                    if result:
                        won = result.get('wonMarkets')
                        result_data = result.get('data')
                        half_lost = result_data.get('halfLostMarkets')
                        half_won = result_data.get('halfWonMarkets')
                        refund_stake = result_data.get('refundMarkets')
                        handicap_data = {'half_lost': half_lost, 'half_won': half_won, 'refund_stake': refund_stake}
                        x = set(won)
                        y = set([str(_) for _ in range(15, 43)])
                        r = list(x & y)
                        z = r[0]
                        score = Markets['Correct_Score'][z]['name'].split('_')
                        results[event_id] = {
                            'id': event_id, 'A': team_a, 'B': team_b,
                            'score': (int(score[1]),
                                      int(score[2]))}
                        result_ids[event_id] = [int(_) for _ in won]
                        winning_ids[event_id] = handicap_data
            self.league_games[week] = matches

            if self.caching:
                self.table.feed_result(e_block_id, league, week, results, result_ids, winning_ids)
        if self.caching:
            missing = self.table.get_missing_weeks()
            if missing:
                e_block_id = self.process_missing(missing)
                await self.next_history(e_block_id, -10)
            else:
                self.caching = False
                logger.debug(f'[{self.user.username}:{self.game_id}] History completed {self.league}')
                await self.dispatch_events()
        else:
            if self.caching_future:
                if not self.is_blocks_complete():
                    blocks = set(i for i in list(self.blocks.keys()))
                    block_id = max(blocks)
                    await self.next_block_future(block_id)
                else:
                    self.caching_future = False
                    self.cached = True
                    logger.debug(f'[{self.user.username}:{self.game_id}] All events cached {self.league}')
                    await self.dispatch_events()

    async def resource_events_process(self, data: Dict):
        self.e_block_id = data.get('eBlockId')
        event_data = data.get('data')
        if not event_data:
            print(data)
        league = event_data.get('leagueId')
        match_day = event_data.get('matchDay')
        if league != self.league:
            # Disable auto skip if running
            if match_day == 1:
                self.auto_skip = False

            self.league_games = {}
            self.blocks = {}
            self.cached = False
            self.required_weeks = self.get_required_weeks()
        self.league = league
        self.week = match_day
        logger.debug(f'[{self.user.username}:{self.game_id}] Event Block: {self.e_block_id} League: {self.league} '
                     f'Week: {self.week}')
        # Generate start time for on demand events
        event_time = data.get('eventTime')
        self.process_event_time(event_time)
        # Parse all events
        events = data.get('events')
        stats = {}
        for event in events:
            event_id = event.get('eventId')
            _data = event.get('data')
            participants = _data.get('participants')
            _data = event.get('data')
            _stats = _data.get('stats')
            stats[event_id] = _stats
            player_a = participants[0]
            player_b = participants[1]
            _id_1 = player_a.get('fifaCode')
            _id_2 = player_b.get('fifaCode')
            _p1 = int(player_a.get('id'))
            _p2 = int(player_b.get('id'))

            # Check if teams in our team labels
            if _p1 not in self.team_labels:
                self.team_labels[_p1] = _id_1
            if _p2 not in self.team_labels:
                self.team_labels[_p2] = _id_2

        if self.auto_skip:
            self.phase = LeagueCompetition.RESULTS
            logger.debug(f'[{self.user.username}:{self.game_id}] Auto skipping league {self.league}')
            await self.next_block_result()
        else:
            # Notify table of events
            self.table.on_event(self.league, self.week)
            self.table.feed_stats(league, self.week, stats)
            missing = self.table.get_missing_weeks()
            if not missing:
                await self.dispatch_events()
            else:
                if self.cached:
                    self.caching_multiple = True
                    for week in missing:
                        await self.next_result(self.get_block_by_week(week), 1)
                else:
                    self.caching = True
                    e_block_id = self.process_missing(missing)
                    await self.next_history(e_block_id, -10)

    async def resource_result_process(self, data: Dict):
        e_block_id = data.get('eBlockId')
        week = self.get_week_by_block(e_block_id)
        logger.debug(f'[{self.user.username}:{self.game_id}] Result Block: {e_block_id} Week : {week}')
        events = data.get('events')
        results = {}
        winning_ids = {}
        result_ids = {}
        for event in events:
            event_id = event.get('eventId')
            result = event.get('result')
            result_data = result.get('data')
            video_url = result_data.get('videoURL')
            half_lost = result_data.get('halfLostMarkets')
            half_won = result_data.get('halfWonMarkets')
            refund_stake = result_data.get('refundMarkets')
            handicap_data = {'half_lost': half_lost, 'half_won': half_won, 'refund_stake': refund_stake}
            video_url = video_url.split('/')
            team_a = self.team_labels.get(int(video_url[4]))
            team_b = self.team_labels.get(int(video_url[5]))
            won = result.get('wonMarkets')
            x = set(won)
            y = set([str(_) for _ in range(15, 43)])
            r = list(x & y)
            z = r[0]
            score = Markets['Correct_Score'][z]['name'].split('_')
            results[event_id] = {
                'id': event_id, 'A': team_a, 'B': team_b,
                'score': (int(score[1]),
                          int(score[2]))}
            # X is won list (wonMarketIds)
            result_ids[event_id] = [int(_) for _ in won]
            winning_ids[event_id] = handicap_data

        if self.auto_skip:
            self.phase = LeagueCompetition.EVENTS
            logger.debug(f'[{self.user.username}:{self.game_id}] Auto skipping league {self.league}')
            await self.next_block_event()
        else:
            self.table.feed_result(e_block_id, self.league, week, results, result_ids, winning_ids)
            if self.caching_multiple:
                missing = self.table.get_missing_weeks()
                if not missing:
                    self.caching_multiple = False
                    for player in self.players.values():
                        pass
                        # if isinstance(punter, Fati):
                        #    await punter.validate_pending_tickets()
                    await self.dispatch_events()

            elif self.fetching_future:
                not_ready = self.table.check_weeks(self.required_weeks)
                if not not_ready:
                    self.fetching_future = False
                    logger.debug(f'[{self.user.username}:{self.game_id}] Future result complete League : {self.league}')
                    await self.dispatch_events()

            else:
                # Notify punters of results
                for player in self.players.values():
                    if player.active:
                        await player.on_result()

                # Attempt to resolve tickets
                await self.user.validate_competition_tickets(self.game_id)

                # Save data to db if final week
                if self.week == self.max_week:
                    await self.on_league_completed()

                if e_block_id == self.e_block_id:
                    self.phase = LeagueCompetition.EVENTS
                    await self.next_block_event()

    async def resource_events_process_resume(self, data: Dict):
        self.restoring = False
        e_block_id = data.get('eBlockId')
        if e_block_id == self.e_block_id:
            logger.debug(f'[{self.user.username}:{self.game_id}] Competition resume success')
            if not self.user.demo:
                if self.active_tickets:
                    if await self.user.resume_competition(self.game_id):
                        # Wait for player to complete ticket
                        logger.info(f'[{self.user.username}:{self.game_id}] resuming tickets')
                    else:
                        await self.next_block_result()
                else:
                    await self.next_block_result()
            else:
                await self.next_block_result()
        else:
            logger.debug(f'[{self.user.username}:{self.game_id}] Competition resume failed')
            await self.user.reset_competition_tickets(self.game_id)
            self.reset_tickets()
            await self.resource_events_process(data)

    async def dispatch_events(self):
        if not self.is_blocks_complete():
            self.caching_future = True
            self.cached = False
            logger.debug(f'[{self.user.username}:{self.game_id}] Caching league {self.league} ')
            await self.next_block_future(self.e_block_id)
        else:
            not_ready = self.table.check_weeks(self.required_weeks)
            if self.future_results and not_ready:
                asyncio.create_task(self.get_future_weeks(not_ready))
            else:
                self.history_count = 0
                tickets_pool = []
                for player in self.players.values():
                    if player.active:
                        tickets = await player.on_event()
                        if tickets:
                            tickets_pool.extend(tickets)
                if tickets_pool:
                    self.phase = LeagueCompetition.TICKETS
                    logger.debug(f'[{self.user.username}:{self.game_id}] Processing tickets : {len(tickets_pool)}')
                    await self.process_tickets(tickets_pool)
                else:
                    self.phase = LeagueCompetition.RESULTS
                    logger.debug(f'[{self.user.username}:{self.game_id}] No Tickets available')
                    await self.next_block_result()

    # API
    def send(self, resource: str, payload: Dict) -> int:
        return self.user.send(self.game_id, resource, payload)

    async def receive(self, xs: int, resource: str, payload: Dict):
        try:
            callback = getattr(self, f'{map_resource_to_name(resource)}_callback')
        except AttributeError:
            pass
        else:
            await callback(xs, resource, payload)

    def modify_player(self, player_name: str, odd_id: str):
        player = self.players.get(player_name)
        if player:
            player.odd_id = int(odd_id)

    def setup_jackpot(self):
        self.jackpot_ready = True
        for player in self.players.values():
            player.setup_jackpot()

    def clear_jackpot(self):
        self.jackpot_ready = False
        for player in self.players.values():
            player.clear_jackpot()

    # Tickets processing
    @async_exception_logger('process')
    async def process_tickets(self, tickets: List):
        self.reset_tickets()
        for ticket in tickets:
            content = self.serialize_ticket(ticket)
            setattr(ticket, 'content', content)
            self.user.register_ticket(ticket)
            await self.user.ticket_manager.add_ticket(ticket)
            self.active_tickets.append(ticket.ticket_key)
        logger.debug(f'[{self.user.username}:{self.game_id}] Processing tickets complete : {len(tickets)}')

    def serialize_ticket(self, ticket):
        events = ticket.events
        event_datas = []
        for event in events:
            event.playlist_id = self.game_id
            event_data = {
                'eventId': event.event_id,
                'gameType': {'val': event.game_type},
                'playlistId': event.playlist_id,
                'eventTime': event.event_time,
                'extId': event.ext_id,
                'isBanker': event.is_banker,
                'finalOutcome': event.final_outcome
            }
            bets = []
            for bet in event.bets:
                bet_data = {
                    'marketId': bet.market_id,
                    'oddId': bet.odd_id,
                    'oddName': bet.odd_name,
                    'oddValue': bet.odd_value,
                    'status': bet.status,
                    'profitType': bet.profit_type,
                    'stake': bet.stake
                }
                bets.append(bet_data)
            event_data['bets'] = bets
            data = {
                'classType': 'FootballTicketEventData',
                'participants': event.participants,
                'leagueId': event.league,
                'matchDay': event.week,
                'eventNdx': event.event_ndx
            }
            event_data['data'] = data
            event_datas.append(event_data)
        ticket_data = {
            'events': event_datas,
            'systemBets': ticket.system_bets,
            'ticketType': ticket.mode
        }
        return ticket_data

    def get_ticket_validation_data(self) -> Tuple[Dict, Dict]:
        return self.table.results_ids_pool, self.table.winning_ids_pool

    async def on_ticket_resolve(self, ticket: Ticket):
        player = self.players.get(ticket.player)
        await player.on_ticket(ticket)

    def reset_tickets(self):
        self.active_tickets = []

    async def on_ticket_complete(self):
        logger.debug(f'[{self.user.username}:{self.game_id}] Tickets completed : {len(self.active_tickets)}')
        self.phase = LeagueCompetition.RESULTS
        await self.next_block_result()

    # Get Weeks info
    def is_blocks_complete(self):
        if len(self.blocks) == self.max_week:
            return True
        return False

    def get_block_by_week(self, week: int):
        for block, w in self.blocks.items():
            if w == week:
                return block

    def get_week_by_block(self, e_block_id: int):
        return self.blocks.get(e_block_id, None)

    def process_missing(self, missing: List):
        if self.cached:
            w = max(missing)
            for week, e_block in self.blocks.items():
                if week == w:
                    return e_block
        else:
            block = self.table.get_min_block()
            if block is None:
                block = self.e_block_id
            return block

    def get_required_weeks(self):
        '''
        weeks = [i for i in range(1, self.max_week + 1)]
        k = [i for i in range(15, self.max_week - 5)]
        r = secrets.choice(k)
        u = [i for i in range(r, r+5)]
        for _ in u:
            weeks.remove(_)
        k.extend([i for i in range(1, 16)])
        return weeks
        '''
        return []
        # return [i for i in range(1, 11)]

    async def get_future_weeks(self, weeks: List[int]):
        self.fetching_future = True
        for week in weeks:
            e_block = self.get_block_by_week(week)
            await asyncio.sleep(0.5)
            await self.next_result(e_block, 1)

    # Event time
    def get_event_time(self):
        now = datetime.now(tz=timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0)
        time_span = int((now - midnight).total_seconds())
        return int(now.timestamp() + self.offset)

    async def await_event_time(self):
        now = int(time.time())
        t = self.event_time - now
        if t > 0:
            await asyncio.sleep(t)

    def process_event_time(self, event_time):
        if event_time is None:
            event_time = time.time() + self.event_time_interval
        self.event_time = event_time

    # Save League
    async def on_league_completed(self):
        if self.table.is_complete():
            league_info = {}
            for week, week_data in self.league_games.items():
                week_results = self.table.get_week_results(week)
                week_stats = self.table.get_week_stats(week)
                week_info = {}
                for event_id, event_data in week_data.items():
                    team_a = event_data.get('A')
                    team_b = event_data.get('B')
                    odds = event_data.get('odds')
                    event_result = week_results.get(event_id)
                    event_stats = week_stats.get(event_id)
                    score = list(event_result.get('score'))
                    week_info[event_id] = {'team_a': team_a, 'team_b': team_b, 'stats': event_stats, 'odds': odds,
                                           'score': score}
                league_info[week] = week_info
            body = {'username': self.user.username, 'league': self.league, 'data': league_info, 'game_id': self.game_id}
            await self.user.store_competition(self.game_id, self.league, league_info)

    # Shutdown
    async def exit(self):
        futures = {}
        for player_id, player in self.players.items():
            player.closing = True
            futures[player_id] = asyncio.create_task(player.shutdown_event.wait())
        done, p = await asyncio.wait(list(futures.values()), return_when=asyncio.ALL_COMPLETED)
        socket = self.user.get_socket(self.game_id)
        await socket.exit()
