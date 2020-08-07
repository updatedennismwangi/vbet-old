from vbet.utils.log import get_logger, exception_logger, async_exception_logger
from typing import Dict, List
from .base import Player
from vbet.game.accounts import RecoverAccount, TokenAccount
from vbet.game.tickets import Ticket, Event, Bet
import numpy


NAME = 'fati'

logger = get_logger(NAME)


class Fati(Player):
    def __init__(self, competition):
        super(Fati, self).__init__(competition)
        self.name = NAME
        self.active = True
        self.min_week = 1

    async def forecast(self):
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        tickets = []
        for event_id, event_data in week_games.items():
            participants = event_data.get('participants')
            odds = event_data.get('odds')
            odd_ids = [0, 1]
            _odds = []
            for odd_id in odd_ids:
                market_id, odd_name, odd_index = Player.get_market_info(str(odd_id))
                _odds.append(odds[odd_index])
            odd_value = max(_odds)
            odd_id = _odds.index(odd_value)
            if odd_id == 0:
                odd_id = 207
            else:
                odd_id = 206
            market_id, odd_name, odd_index = Player.get_market_info(str(odd_id))
            odd_value = float(odds[odd_index])
            if odd_value < 1.3:
                continue
            ticket = Ticket(self.competition.game_id, self.name)
            event = Event(event_id, self.competition.league, self.competition.week, participants)
            stake = 50
            bet = Bet(odd_id, market_id, odd_value, odd_name, stake)
            event.add_bet(bet)
            win = round(stake * odd_value, 2)
            min_win = win
            max_win = win
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
