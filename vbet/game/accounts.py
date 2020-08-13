from __future__ import annotations

import asyncio
from typing import Dict, List, Tuple, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from vbet.game.user import User


class AccountManager:
    MIN_BET_AMOUNT = 5
    profit: int
    _lost_amount: int

    def __init__(self, user: User, credit: float = 100000):
        self.user: User = user
        self.setup(credit)
        self._credit: float = credit
        self.credit_lock: asyncio.Lock = asyncio.Lock()
        self.lost_lock: asyncio.Lock = asyncio.Lock()
        self.won_lock: asyncio.Lock = asyncio.Lock()
        self._bonus_level: int = 0
        self.bonus_mode: bool = False
        self.bonus_total: float = 0
        self._jackpot_amount: float = 25
        self._levels: List[float] = [25, 50, 125, 500, 1250, 2500]
        self._total_stake: float = 0
        self.recover_account: RecoverAccountShare = RecoverAccountShare(self)
        self.initialized: bool = False

    async def initialize(self):
        self.initialized = True

    @property
    def total_stake(self):
        return self._total_stake

    @total_stake.setter
    def total_stake(self, stake: float):
        self._total_stake += stake

    @property
    def bonus_level(self):
        return self._bonus_level

    @bonus_level.setter
    def bonus_level(self, level: int):
        if level is None:
            level = -1
        self._bonus_level = level

    @property
    def jackpot_amount(self):
        return self._jackpot_amount

    @property
    def jackpot_value(self):
        if self._bonus_level > -1:
            top_limit = self._levels[self.bonus_level]
            return round((self.jackpot_amount / top_limit) * 100, 2)
        return 0

    @jackpot_amount.setter
    def jackpot_amount(self, amount):
        self._jackpot_amount = float(amount)

    def is_bonus_ready(self) -> bool:
        if self.bonus_mode:
            if self.total_stake >= self.bonus_total:
                return True
        else:
            if self._bonus_level == 6:
                bonus_amount = self._levels[-1]
                a = (self._jackpot_amount / bonus_amount) * 100
                return a >= 99.3
        return False

    def setup(self, credit: float):
        self._credit = credit
        self.profit = 0
        self._lost_amount = 0

    @property
    async def credit(self):
        async with self.credit_lock:
            if self.user.demo:
                return round(self._credit, 2)
            return self._credit

    async def update(self, credit: float):
        async with self.credit_lock:
            self._credit = credit

    async def fund(self, credit: float):
        async with self.credit_lock:
            self._credit += credit

    async def on_win(self, credit: float):
        if self.user.demo:
            await self.fund(credit)

    async def on_loose(self, credit: float):
        async with self.lost_lock:
            self._lost_amount += credit

    async def borrow(self, amount) -> Tuple[bool, Union[float, None]]:
        amount = round(amount, 2)
        async with self.credit_lock:
            if self._credit >= amount:
                self._credit -= amount
                return True, amount
        return False, None

    def normalize_amount(self, amount) -> float:
        game_settings = self.user.settings.get_val_settings('GL')
        if game_settings:
            min_stake = game_settings.get('min_stake', 0)
            max_stake = game_settings.get('max_stake', 0)
            if amount < min_stake:
                amount = min_stake
            if amount > max_stake:
                amount = max_stake
        if amount < self.MIN_BET_AMOUNT:
            amount = self.MIN_BET_AMOUNT
        return round(amount, 2)


class Account:
    def __init__(self, manager: AccountManager):
        self.manager: AccountManager = manager
        self._won_amount = 0
        self._initial_token = 5
        self._lost_amount = self._initial_token
        self._profit_token = 0
        self.max_stake = 100000

    @property
    def lost_amount(self):
        return self._lost_amount

    def reset_lost_amount(self):
        self._lost_amount = self._initial_token

    def setup(self, config: Dict):
        pass

    async def on_win(self, amount: float):
        await self.manager.on_win(amount)
        self._won_amount += amount

    async def on_loose(self, amount: float):
        await self.manager.on_loose(amount)
        self._lost_amount += amount

    def normalize_stake(self, amount: float):
        return self.manager.normalize_amount(amount)


class RecoverAccount(Account):
    def __init__(self, manager: AccountManager):
        super(RecoverAccount, self).__init__(manager)
        self.amount_lost: float = self._initial_token
        self.max_stake_lost: float = 100000

    def get_stake(self, odd: float) -> float:
        stake = self.amount_lost / (odd - 1)
        if stake > self.max_stake or (stake + self.amount_lost) > self.max_stake_lost:
            self.amount_lost = self._initial_token
            stake = self.amount_lost / (odd - 1)
        return stake

    async def on_win(self, amount: float):
        await super().on_win(amount)
        self.amount_lost = self._initial_token

    async def on_loose(self, amount: float):
        await super().on_loose(amount)
        self.amount_lost += (amount + self._profit_token)


class TokenAccount(Account):
    def __init__(self, manager: AccountManager):
        super(TokenAccount, self).__init__(manager)
        self.chips = [100, 150, 75, 75, 100]
        self.index = 0

    def get_stake(self) -> float:
        return self.chips[self.index]

    async def on_win(self, amount: float):
        await super().on_win(amount)
        if self.index > 0:
            self.index = 0

    async def on_loose(self, amount: float):
        if self.index < len(self.chips):
            self.index += 1
        else:
            self.index = 0
        await super().on_loose(amount)


class FixedStake(Account):
    def __init__(self, manager: AccountManager, stake: float):
        super(FixedStake, self).__init__(manager)
        self.stake: float = stake

    def get_stake(self) -> float:
        return self.stake


class FixedProfitAccount(Account):
    def __init__(self, manager: AccountManager):
        super(FixedProfitAccount, self).__init__(manager)
        self.profit = 5

    def get_stake(self, odd_value: float) -> float:
        return round(self.profit / (odd_value - 1), 2)


class RecoverAccountShare(Account):
    def __init__(self, manager: AccountManager):
        super(RecoverAccountShare, self).__init__(manager)
        self.amount_lost = self._initial_token

    def get_stake(self, odd_value: float) -> float:
        stake = (self.amount_lost / 4) / (odd_value - 1)
        return stake

    async def on_win(self, amount: float):
        await super().on_win(amount)
        self.amount_lost -= amount
        if self.amount_lost < self._initial_token:
            self.amount_lost = self._initial_token

    async def on_loose(self, amount: float):
        await super().on_loose(amount)
        self.amount_lost += (amount + self._profit_token)


