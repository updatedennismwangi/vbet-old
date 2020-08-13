from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from vbet.game.accounts import Account
from vbet.game.markets import Markets
from vbet.game.tickets import Ticket
from vbet.utils.log import get_logger

if TYPE_CHECKING:
    from vbet.game.competition import LeagueCompetition


NAME = 'player'

logger = get_logger('player')


class Player:
    def __init__(self, competition: LeagueCompetition, name: str = None):
        self.competition: LeagueCompetition = competition
        self.min_week: int = 1
        self.league: Optional[int] = None
        self.current_league_complete: bool = False
        self._active: bool = False
        self.closing: bool = False
        self.name: str = name if name else NAME
        self.bet_ready: bool = False
        self.jackpot_ready: bool = False
        self._bet: bool = False
        self._forecast: bool = True
        self.odd_id: Optional[int] = None
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.shutdown_event.set()
        self.account: Account = Account(self.competition.user.account_manager)
        self.required_weeks: List[int] = [i for i in range(1, self.competition.max_week + 1)]

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

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

    async def on_event(self) -> List[Ticket]:
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

    async def on_ticket_resolve(self, ticket: Ticket):
        pass

    async def forecast(self) -> List[Ticket]:
        tickets = []  # type: List[Ticket]
        return tickets

    def can_bet(self) -> bool:
        return self._bet

    def can_forecast(self) -> bool:
        if self.current_league_complete:
            return False
        if self.competition.week < self.min_week:
            return False
        return self._forecast

    def setup_jackpot(self):
        self.jackpot_ready = True

    def clear_jackpot(self):
        self.jackpot_ready = False

    @staticmethod
    def get_result_ratio(last_result: List[str]) -> Tuple[int, int]:
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
    def pick_winner(head_to_head: List[List[str]], draw=False) -> Tuple[Any, Any]:
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
    def get_market_info(market: str) -> Tuple[Any, Any, Any]:
        for market_type, market_data in Markets.items():
            if market in market_data:
                data = market_data.get(market)
                if data:
                    return market_type, data.get('name'), int(data.get('key'))
        return None, None, None

    def get_required_weeks(self):
        self.required_weeks = [i for i in range(1, self.competition.max_week + 1)]

    async def exit(self):
        await self.shutdown_event.wait()
