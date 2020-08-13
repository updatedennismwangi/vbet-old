import argparse
import os
import sys

import asynccmd
import websockets

import vbet
from vbet.game.competition import *
from vbet.utils.parser import decode_json, encode_json


class Vshell(asynccmd.Cmd):
    def __init__(self, host, port):
        super().__init__(mode="Reader")
        self.host: str = host
        self.port: int = port
        self.server_url: str = f'ws://{self.host}:{self.port}'
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.prompt: str = '$ > '
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

    @property
    def intro(self):
        return f'\nVshell url={self.server_url} build v{vbet.__VERSION__}\n\nType (help) to see a list of ' \
               f'available commands\n'

    @property
    def commands(self):
        commands = []
        for i in dir(self.__class__):
            if i.startswith('do_'):
                a = i.split('_')
                if len(a) == 2:
                    commands.append(a[1])
        return commands

    def run(self):
        self.loop = asyncio.get_event_loop()
        try:
            self.loop.run_until_complete(self.event_loop())
        except KeyboardInterrupt:
            self.loop.stop()

    async def event_loop(self):
        try:
            async with websockets.connect(self.server_url, close_timeout=0.1) as websocket:
                self.websocket = websocket
                super()._start_reader()
                while True:
                    try:
                        payload = await websocket.recv()
                        data = decode_json(payload)
                        uri = data.get('uri')
                        body = data.get('body')
                        sys.stdout.write(f'\r>>> {uri} {body}\n {self.prompt}')
                    except websockets.ConnectionClosed:
                        break
        except ConnectionError:
            pass
        finally:
            raise KeyboardInterrupt

    async def send(self, uri, body):
        payload = {'uri': uri, 'body': body}
        await self.websocket.send(encode_json(payload))

    def do_add(self, arg):
        arg = arg.split(' ')
        if arg:
            username = arg[0]
            demo = True
            try:
                demo = int(arg[1])
                demo = False if demo == 1 else True
            except (IndexError, ValueError):
                pass
            if len(username) > 0:
                games = arg[2:]
                if not games:
                    games = settings.LIVE_GAMES
                body = {'username': username, 'demo': demo, 'games': games}
                self.loop.create_task(self.send('add', body))
                print(body)
            else:
                print(self.do_str_add())
        else:
            print(self.do_str_add())

    def do_login(self, arg):
        arg = arg.split(' ')
        if arg and len(arg) >= 2:
            username = arg[0]
            password = arg[1]
            body = {'username': username, 'password': password}
            self.loop.create_task(self.send('login', body))
            print(body)
        else:
            print(self.do_str_login())

    def do_help(self, arg):
        if arg:
            arg = arg.split(' ')
            command = str(arg[0])
            func_name = f'do_str_{command}'
            handler = getattr(Vshell, func_name, None)
            if handler:
                print(handler())
            else:
                print(super()._default(command))
        else:
            for i in dir(self.__class__):
                if i.startswith('do_str'):
                    handler = getattr(self, i)
                    print(i[7:], '-', handler())

    def do_exit(self, arg):
        self.loop.create_task(self.send('exit', {}))

    @staticmethod
    def do_clear(arg):
        os.system('clear')

    @staticmethod
    def do_quit(arg):
        print('Terminated Shell')
        raise KeyboardInterrupt

    @staticmethod
    def do_str_add():
        return f'Add user to system Usage: add <username> <demo> <games>'

    @staticmethod
    def do_str_login():
        return f'Login user and cache Usage: login <username> <password>'

    @staticmethod
    def do_str_test():
        return f'Run application tests'

    @staticmethod
    def do_str_clear():
        return 'Clear screen output'

    @staticmethod
    def do_str_exit():
        return 'Send Exit to server'

    @staticmethod
    def do_str_quit():
        return f'Exit the shell'

    def _emptyline(self, line):
        """
        handler for empty line if entered.
        """
        pass


def vshell():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--host', default=settings.WS_HOST, help=f'Vshell server host. Default {settings.WS_HOST}')
    arg_parser.add_argument('-p', default=settings.WS_PORT, type=int, help=f'Server port. Default {settings.WS_PORT}')
    args = arg_parser.parse_args(sys.argv[1:])
    vs = Vshell(args.host, args.p)
    vs.run()
