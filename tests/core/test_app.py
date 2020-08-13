import pytest
import asyncio

from vbet.core.app import application, parse_args
from vbet.core.vbet import EXIT_SUCCESS, EXIT_INTERRUPT


class TestApp:
    def test_keyboard_interrupt(self, event_loop):
        event_loop.call_later(5, self.stop_application)
        exit_code = application([])
        assert exit_code == EXIT_SUCCESS

    @staticmethod
    def stop_application():
        raise KeyboardInterrupt

