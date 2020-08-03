from vbet.utils.log import get_logger, exception_logger, async_exception_logger
from typing import Dict, List
from .base import Player
from vbet.game.accounts import RecoverAccount, TokenAccount
from vbet.game.tickets import Ticket, Event, Bet
import secrets
from collections import Counter


NAME = 'neymar'

logger = get_logger(NAME)


class Neymar(Player):
    def __init__(self, competition):
        super(Neymar, self).__init__(competition)
        self.name = NAME
        self.active = True
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.team = None
        self.event_id = None
        self.event_data = {}
        self.odd_id = 0
        self.last_team = None

    """
    def predict(self, week):
        pass
        '''
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        stats = self.competition.table.get_week_stats(week)
        for event_id, event_data in week_games.items():
            player_a = event_data.get('A')
            player_b = event_data.get('B')
            event_stats = stats.get(event_id)
            targets = ['BAR', 'RMA']
            if player_a in targets and player_b in targets:
                if event_stats:
                    team_to_team = event_stats.get('teamToTeam')
                    head_to_head = team_to_team.get('headToHead')
                    # last_result = team_to_team.get('lastResult')
                    event_valid = True
                    for score in head_to_head:
                        a = int(score[0])
                        b = int(score[1])
                        if (a + b) > 2:
                            continue
                        else:
                            event_valid = False
                            break
                    if event_valid:
                        self.team = player_a
                    if self.team:
                        break
        '''
    """
    async def forecast(self):
        if not self.team:
            return []
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        for event_id, event_data in week_games.items():
            player_a = event_data.get('A')
            player_b = event_data.get('B')
            if player_a == self.team or player_b == self.team:
                self.event_id = event_id
                self.event_data = event_data
                self._bet = True
                if player_a == self.team:
                    self.odd_id = 210
                else:
                    self.odd_id = 211
                break

        odds = self.event_data.get('odds')
        participants = self.event_data.get('participants')
        ticket = Ticket(self.competition.game_id, self.name)
        event = Event(self.event_id, self.competition.league, self.competition.week, participants)
        market_id, odd_name, odd_index = Player.get_market_info(str(self.odd_id))
        odd_value = float(odds[odd_index])
        if odd_value < 1.02:
            return []
        # stake = self.account.normalize_stake(self.account.get_recover_amount(odd_value))
        stake = 100
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
        return [ticket]

    async def on_result(self):
        # if self.competition.week == self.competition.max_week:
        self.team = self.competition.table.table[-1].get('team')

    async def on_ticket_resolve(self, ticket: Ticket):
        pass
