from typing import Dict, List

from vbet.game.accounts import RecoverAccount
from vbet.game.tickets import Bet, Event, Ticket
from vbet.utils.log import get_logger
from .base import Player

NAME = 'hazard'

logger = get_logger(NAME)


class CustomPlayer(Player):
    def __init__(self, competition):
        super(CustomPlayer, self).__init__(competition, NAME)
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.team = None
        self.event_id = None
        self.event_data = {}
        self.odd_id = 0
        self.bet_enabled = False
        self.min_week = 2
        self.shutdown_event.set()

    def can_forecast(self):
        return super().can_forecast()

    async def forecast(self):
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        if not self.bet_enabled:
            table = self.competition.table.table  # type: List[Dict]
            targets = table[:2]
            points = []
            for target_team in targets:
                team = target_team.get('team')
                p = target_team.get('points')
                points.append((team, p))
            if points:
                first = points[0]
                second = points[1]
                f_p = first[1]
                s_p = second[1]
                if f_p - s_p > 15:
                    self.team = first[0]
                    self.bet_enabled = True
                    print(points)
                if not self.bet_enabled or self.competition.week not in self.required_weeks:
                    return []
            else:
                return []
        if not self.bet_enabled:
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
        stake = self.account.get_stake(odd_value)
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

    async def on_ticket_resolve(self, ticket: Ticket):
        if ticket.total_won > 0:
            self.bet_enabled = False
            self.team = None
            self.current_league_complete = True

    def get_required_weeks(self):
        super().get_required_weeks()
