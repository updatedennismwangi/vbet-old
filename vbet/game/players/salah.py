from vbet.utils.log import get_logger, exception_logger, async_exception_logger
from typing import Dict, List
from .base import Player
from vbet.game.accounts import RecoverAccount
from vbet.game.tickets import Ticket, Event, Bet
import secrets


NAME = 'salah'

logger = get_logger(NAME)


class Salah(Player):
    def __init__(self, competition):
        super(Salah, self).__init__(competition)
        self.name = NAME
        self.active = True
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.team = None
        self.event_id = None
        self.event_data = {}
        self.odd_id = 0
        self.max_turn = 5
        self.live_turn = 0
        self.live_league = None
        self.shutdown_event.set()

    def can_forecast(self):
        if self.competition.week < 10:
            return False
        return self._forecast

    async def forecast(self):
        table = self.competition.table.table  # type: List[Dict]
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        self.live_turn += 1
        if not self.team or (self.live_turn > self.max_turn) or (self.live_league != self.competition.league):
            team = table[0].get('team')
            self.live_turn = 0
            upcoming = [league_games.get(i, None) for i in range(self.competition.week, self.competition.week +
                                                           self.max_turn)]
            valid = True
            v = []
            for week_games in upcoming:
                if week_games:
                    for event_id, event_data in week_games.items():
                        player_a = event_data.get('A')
                        player_b = event_data.get('B')
                        odds = event_data.get('odds')
                        if player_a == self.team or player_b == self.team:
                            if player_a == self.team:
                                odd_id = 207
                            else:
                                odd_id = 206
                            market_id, odd_name, odd_index = Player.get_market_info(str(odd_id))
                            odd_value = float(odds[odd_index])
                            if odd_value < 1.3:
                                valid = False
                                break
                            else:
                                v.append(odd_value)
                else:
                    valid = False
                    break
            if valid:
                self.team = team

        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        for event_id, event_data in week_games.items():
            player_a = event_data.get('A')
            player_b = event_data.get('B')
            if player_a == self.team or player_b == self.team:
                self.event_id = event_id
                self.event_data = event_data
                if player_a == self.team:
                    self.odd_id = 207
                else:
                    self.odd_id = 206
                self._bet = True
                break
            else:
                continue

        odds = self.event_data.get('odds')
        participants = self.event_data.get('participants')
        ticket = Ticket(self.competition.game_id, self.name)
        event = Event(self.event_id, self.competition.league, self.competition.week, participants)
        market_id, odd_name, odd_index = Player.get_market_info(str(self.odd_id))
        odd_value = float(odds[odd_index])
        if odd_value < 1.02:
            return []
        stake = self.account.normalize_stake(50)
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
