from vbet.utils.log import get_logger, exception_logger, async_exception_logger
from typing import Dict, List
from .base import Player
from vbet.game.accounts import RecoverAccount
from vbet.game.tickets import Ticket, Event, Bet
import secrets


NAME = 'ronaldo'

logger = get_logger(NAME)


class Ronaldo(Player):
    def __init__(self, competition):
        super(Ronaldo, self).__init__(competition)
        self.name = NAME
        self.active = True
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.team = None
        self.event_id = None
        self.event_data = {}
        self.odd_id = 0

    def can_forecast(self):
        if self.competition.week < 8:
            return False
        return self._forecast

    @async_exception_logger('forecast')
    async def forecast(self):
        table = self.competition.table.table  # type: List[Dict]
        self.team = table[0].get('team')
        league_games = self.competition.league_games  # type: Dict[int, Dict]
        week_games = league_games.get(self.competition.week)  # type: Dict[int, Dict]
        for event_id, event_data in week_games.items():
            player_a = event_data.get('A')
            player_b = event_data.get('B')
            if player_a == self.team or player_b == self.team:
                self.event_id = event_id
                self.event_data = event_data
                self._bet = True
                break
            else:
                continue

        odds = self.event_data.get('odds')
        participants = self.event_data.get('participants')
        ticket = Ticket(self.competition.game_id, self.name)
        event = Event(self.event_id, self.competition.league, self.competition.week, participants)
        ticket.add_event(event)
        min_win = 0
        max_win = 0
        total_stake = 0
        a = [i for i in range(15, 43)]
        b = []
        for _ in a:
            market_id, odd_name, odd_index = Player.get_market_info(str(_))
            b.append(1 / float(odds[odd_index]))
        target_odd_ids = secrets.SystemRandom().choices(a, b, k=20)
        for odd_id in [73, 75]:
            market_id, odd_name, odd_index = Player.get_market_info(str(odd_id))
            odd_value = float(odds[odd_index])
            if odd_value < 1.02:
                return []
            stake = self.account.normalize_stake(10)
            total_stake += stake
            bet = Bet(odd_id, market_id, odd_value, odd_name, stake)
            event.add_bet(bet)
            win = round(stake * odd_value, 2)
            min_win = win if win < min_win else min_win
            max_win = win if max_win > max_win else max_win
            logger.info(f'[{self.competition.user.username}:{self.competition.game_id}] {self.name} '
                         f'{event.get_formatted_participants()}[{odd_id} : {odd_value}]')
        ticket.stake = total_stake
        ticket.min_winning = min_win
        ticket.max_winning = max_win
        ticket.total_won = 0
        ticket.grouping = 1
        ticket.winning_count = len(target_odd_ids)
        ticket.system_count = len(target_odd_ids)
        return [ticket]
