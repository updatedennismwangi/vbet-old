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
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.odd_id = 55
        self.min_week = 1

    async def forecast(self):
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        tickets = []
        for event_id, event_data in week_games.items():
            # player_a = event_data.get('A')
            # player_b = event_data.get('B')
            participants = event_data.get('participants')
            market_id = 'FullTimeUnderOver2_5GoalGoalNoGoal'
            odd_name = "HomeOver2_5GoalGoal"
            all_odds = [i for i in numpy.arange(2, 15, 0.01)]
            for odd_value in all_odds:
                odd_value = round(odd_value, 2)
                ticket = Ticket(self.competition.game_id, self.name)
                event = Event(event_id, self.competition.league, self.competition.week, participants)
                stake = 5
                bet = Bet(self.odd_id, market_id, odd_value, odd_name, stake)
                event.add_bet(bet)
                win = round(stake * odd_value, 2)
                min_win = win
                max_win = win
                # logger.info(f'[{self.competition.user.username}:{self.competition.game_id}] {self.name} '
                #              f'{event.get_formatted_participants()}[{self.odd_id} : {odd_value}]')
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
        event = ticket.events[0]
        par = event.get_formatted_participants()
        par_text = f'{par[0]}_{par[1]}'
        bet = event.bets[0]
        bet_data = bet.__str__()
        f = open(f'{par_text}.txt', 'w')
        f.write(f'{bet_data}')
        f.close()
