from vbet.utils.log import get_logger, exception_logger
from typing import Dict, List
from abc import abstractmethod
from vbet.game.markets import Markets
from vbet.game.accounts import Account
from vbet.game.tickets import Ticket, Event, Bet
import asyncio


logger = get_logger('player')
account_logger = get_logger('account')


class Player:
    def __init__(self, competition, name="player"):
        self.competition = competition
        self.min_week = 1
        self.league = None
        self.current_league_complete = False
        self._active = False
        self.closing = False
        self.name = name
        self.bet_ready = False
        self.jackpot_ready = False
        self._bet = False
        self._forecast = True
        self.odd_id: int = None
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.account: Account = Account(self.competition.user.account_manager)

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, state: bool):
        self._active = state
        if state:
            logger.debug(f'[{self.competition.user.username}:{self.competition.game_id}] {self.name} Activated')
        else:
            logger.debug(f'[{self.competition.user.username}:{self.competition.game_id}] {self.name} Deactivated')

    async def on_event(self):
        if self.competition.league != self.league:
            self.league = self.competition.league
            self.current_league_complete = False

        self._bet = False
        tickets = []  # type: List[Ticket]
        if self.can_forecast():
            tickets = await self.forecast()
        return tickets

    async def on_result(self):
        pass

    async def on_ticket(self, ticket: Ticket):
        stake = ticket.stake
        if ticket.total_won < stake:
            await self.account.on_loose(stake)
        else:
            await self.account.on_win(ticket.total_won)
        await self.on_ticket_resolve(ticket)
        '''
        credit = await self.account.manager.credit
        account_logger.info(f'[{self.competition.user.username}:{self.competition.game_id}] {self.name} '
                            f'Bal : {credit:.2f} Bonus: [L{self.account.manager.bonus_level + 1} : '
                            f'{self.account.manager.jackpot_value}%] ['
                            f'{self.account.manager.jackpot_amount:.2f}] Won :'
                            f' {ticket.total_won:.2f} Stake : ['
                            f'{self.account.manager.total_stake:.2f}]')
        '''

    async def on_ticket_resolve(self, ticket: Ticket):
        pass

    async def forecast(self):
        tickets = []  # type: List[Ticket]
        return tickets

    def can_bet(self):
        return self._bet

    def can_forecast(self):
        if self.competition.week < self.min_week or self.current_league_complete:
            return False
        return self._forecast

    def setup_jackpot(self):
        self.jackpot_ready = True

    def clear_jackpot(self):
        self.jackpot_ready = False

    @staticmethod
    def get_result_ratio(last_result: List[str]):
        home_result = []
        away_result = []
        home_ratio = 0
        away_ratio = 0
        for result in last_result:
            home = result[0]
            away = result[1]
            if home == "W":
                home_result.append(3)
                home_ratio += 20
            elif home == "D":
                home_result.append(1)
            else:
                home_result.append(0)
            if away == "W":
                away_result.append(3)
                away_ratio += 20
            elif away == "D":
                away_result.append(1)
            else:
                away_result.append(0)
        return home_ratio, away_ratio

    @staticmethod
    def pick_winner(head_to_head: List[List[str]], draw=False):
        a = 0
        b = 0
        c = 0
        if len(head_to_head) >= 5:
            for result in head_to_head:
                home_goals = int(result[0])
                away_goals = int(result[1])
                if home_goals > away_goals:
                    a += 1
                elif home_goals < away_goals:
                    b += 1
                else:
                    c += 1
            if draw:
                a += c
                b += c
            if a > b:
                return 0, a
            elif b > a:
                return 1, b
            else:
                return 2, a
        return None, None

    @staticmethod
    def get_market_info(market: str):
        for market_type, market_data in Markets.items():
            if market in market_data:
                data = market_data.get(market)
                if data:
                    return market_type, data.get('name'), int(data.get('key'))
        return None, None, None

    async def shutdown(self):
        return self.terminate()

    async def terminate(self):
        await self.shutdown_event.wait()
