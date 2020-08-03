from vbet.utils.log import get_logger, exception_logger, async_exception_logger
from typing import Dict, List
from .base import Player
from vbet.game.accounts import RecoverAccount, TokenAccount
from vbet.game.tickets import Ticket, Event, Bet
import secrets
import numpy
from collections import Counter


NAME = 'arthur'

logger = get_logger(NAME)


class Arthur(Player):
    def __init__(self, competition):
        super(Arthur, self).__init__(competition)
        self.name = NAME
        self.active = True
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.team = 'RMA'
        self.event_id = None
        self.event_data = {}
        self.odd_id = 55
        self.min_week = 1

    async def forecast(self):
        if not self.team:
            return []
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        for event_id, event_data in week_games.items():
            player_a = event_data.get('A')
            player_b = event_data.get('B')
            if player_a == 'BET' and player_b == self.team:
                self.event_id = event_id
                self.event_data = event_data
                self._bet = True
                break
        if not self._bet:
            return []
        participants = self.event_data.get('participants')
        market_id = 'FullTimeUnderOver2_5GoalGoalNoGoal'
        odd_name = "HomeOver2_5GoalGoal"
        all_odds = [i for i in numpy.arange(1.02, 15, 0.01)]
        tickets = []
        # all_odds = [4.44]
        # all_odds = [7.7]
        # all_odds = [7.79]
        # all_odds = [3.35]
        for odd_value in all_odds:
            odd_value = round(odd_value, 2)
            ticket = Ticket(self.competition.game_id, self.name)
            event = Event(self.event_id, self.competition.league, self.competition.week, participants)
            stake = 5
            bet = Bet(self.odd_id, market_id, odd_value, odd_name, stake)
            event.add_bet(bet)
            win = round(stake * odd_value, 2)
            min_win = win
            max_win = win
            logger.info(f'[{self.competition.user.username}:{self.competition.game_id}] {self.name} '
                         f'{event.get_formatted_participants()}[{self.odd_id} : {odd_value}]')
            ticket.add_event(event)
            ticket.stake = stake
            ticket.min_winning = min_win
            ticket.max_winning = max_win
            ticket.total_won = 0
            ticket.grouping = 1
            ticket.winning_count = 1
            ticket.system_count = 1
            tickets.append(ticket)
        return tickets

    async def on_ticket_resolve(self, ticket: Ticket):
        pass
