from vbet.utils.log import get_logger, exception_logger, async_exception_logger
from typing import Dict, List
from .base import Player
from vbet.game.accounts import RecoverAccount
from vbet.game.tickets import Ticket, Event, Bet
import secrets


NAME = 'hazard'

logger = get_logger(NAME)


class Hazard(Player):
    def __init__(self, competition):
        super(Hazard, self).__init__(competition)
        self.name = NAME
        self.active = True
        self.account = RecoverAccount(self.competition.user.account_manager)
        self.team = None
        self.event_id = None
        self.event_data = {}
        self.odd_id = 0
