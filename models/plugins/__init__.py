from __future__ import annotations

import importlib
import pkgutil


def discover_plugins(package_name: str = "models.providers") -> list[str]:
    package = importlib.import_module(package_name)
    if not hasattr(package, "__path__"):
        return []

    loaded: list[str] = []
    prefix = package.__name__ + "."
    for module_info in pkgutil.iter_modules(package.__path__, prefix):
        importlib.import_module(module_info.name)
        loaded.append(module_info.name)
    return loaded
