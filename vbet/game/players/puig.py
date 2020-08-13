from typing import Dict

from vbet.game.accounts import RecoverAccount
from vbet.game.tickets import Bet, Event, Ticket
from vbet.utils.log import get_logger
from .base import Player

NAME = 'fati'

logger = get_logger(NAME)


class CustomPlayer(Player):
    def __init__(self, competition):
        super(CustomPlayer, self).__init__(competition, NAME)
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.min_week = 1

    async def forecast(self):
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        tickets = []
        for event_id, event_data in week_games.items():
            # player_a = event_data.get('A')
            # player_b = event_data.get('B')
            participants = event_data.get('participants')
            odds = event_data.get('odds')
            odd_ids = [0, 1]
            _odds = []
            for odd_id in odd_ids:
                market_id, odd_name, odd_index = Player.get_market_info(str(self.odd_id))
                _odds.append(odds[odd_index])
            all_odds = [odds[odd_index]]
            # market_id = 'FullTimeUnderOver2_5GoalGoalNoGoal'
            # odd_name = "HomeOver2_5GoalGoal"
            # all_odds = []
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
        return
        event = ticket.events[0]
        par = event.get_formatted_participants()
        par_text = f'{par[0]}_{par[1]}'
        bet = event.bets[0]
        bet_data = bet.__str__()
        f = open(f'{par_text}.txt', 'w')
        f.write(f'{bet_data}')
        f.close()
