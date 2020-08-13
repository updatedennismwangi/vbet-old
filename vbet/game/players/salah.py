from typing import Dict, List

from vbet.game.accounts import RecoverAccount
from vbet.game.tickets import Bet, Event, Ticket
from vbet.utils.log import get_logger
from .base import Player

NAME = 'salah'

logger = get_logger(NAME)


class CustomPlayer(Player):
    def __init__(self, competition):
        super(CustomPlayer, self).__init__(competition, NAME)
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.team = None
        self.prev_team = None
        self.event_id = None
        self.event_data = {}
        self.odd_id = 0
        self.shutdown_event.set()

    def can_forecast(self):
        return self._forecast

    async def forecast(self):
        table = self.competition.table.table  # type: List[Dict]
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        if self.competition.week == self.competition.max_week:
            self.prev_team = table[0].get('team')
        if not self.team or self.competition.week not in self.required_weeks:
            return []
        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        for event_id, event_data in week_games.items():
            player_a = event_data.get('A')
            player_b = event_data.get('B')
            if player_a == self.team or player_b == self.team:
                self.event_id = event_id
                self.event_data = event_data
                if player_a == self.team:
                    self.odd_id = 0
                else:
                    self.odd_id = 1
                self._bet = True
                break
            else:
                continue
        if not self._bet:
            return []
        odds = self.event_data.get('odds')
        participants = self.event_data.get('participants')
        ticket = Ticket(self.competition.game_id, self.name)
        event = Event(self.event_id, self.competition.league, self.competition.week, participants)
        market_id, odd_name, odd_index = Player.get_market_info(str(self.odd_id))
        odd_value = float(odds[odd_index])
        if odd_value < 1.02:
            return []
        stake = self.account.normalize_stake(self.account.get_stake(odd_value))
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
        # print(ticket)
        return [ticket]

    def get_required_weeks(self):
        self.team = self.prev_team
        if self.team:
            required_weeks = []
            league_games = self.competition.league_games  # type: Dict[int, Dict]
            for week, week_games in league_games.items():
                for event_id, event_data in week_games.items():
                    player_a = event_data.get('A')
                    player_b = event_data.get('B')
                    odds = event_data.get('odds')
                    if player_a == self.team or player_b == self.team:
                        if player_a == self.team:
                            odd_id = 0
                        else:
                            odd_id = 1
                        market_id, odd_name, odd_index = Player.get_market_info(str(odd_id))
                        odd_value = float(odds[odd_index])
                        if 1.9 > odd_value > 1.4:
                            if week not in required_weeks:
                                required_weeks.append(week)
            if len(required_weeks) >= 5:
                self.required_weeks = required_weeks
        else:
            super().get_required_weeks()
