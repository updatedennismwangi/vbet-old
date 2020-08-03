#!/home/update/Desktop/www/venv/bin/python

import os
import sys
import inspect

exec_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
app_dir = os.path.dirname(exec_dir)
sys.path.insert(0, app_dir)

from vbet.core.settings import setup


if __name__ == "__main__":
    # App configuration and setup
    setup()

    import vbet.utils.logger
    from vbet.core.app import Vbet

    app = Vbet()
    app.run()