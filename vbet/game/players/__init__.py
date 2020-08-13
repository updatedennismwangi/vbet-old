from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

from .base import Player

__all__ = []
package_dir = Path(__file__).resolve().parent
modules = []
for (_, module_name, _) in iter_modules([package_dir]):
    module = import_module(f"{__name__}.{module_name}")
    name = getattr(module, 'NAME', None)
    if name:
        if name != 'player':
            cls = getattr(module, 'CustomPlayer')
            setattr(module, name.capitalize(), type(name.capitalize(), (cls,), {}))


