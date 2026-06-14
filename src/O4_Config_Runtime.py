"""Runtime-only global config loading for O4_Config_Utils.

This module exists so importing O4_Config_Utils can stay side-effect-free while
the file I/O and cross-module default assignment remain explicit and testable.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import O4_UI_Utils as UI
from O4_Config_Models import UnsupportedWaterTechError

_initialized_namespaces: set[int] = set()


def is_initialized(namespace: dict[str, Any]) -> bool:
    """Return whether the config namespace has completed runtime initialization."""
    return id(namespace) in _initialized_namespaces


def initialize_from_namespace(
    namespace: dict[str, Any], *, force: bool = False
) -> None:
    """Initialize config using the public/private bindings from O4_Config_Utils."""
    if is_initialized(namespace) and not force:
        return
    GlobalConfigRuntime(
        cfg_vars=namespace["cfg_vars"],
        cfg_global_tile_vars=namespace["cfg_global_tile_vars"],
        cfg_app_vars=namespace["cfg_app_vars"],
        global_prefix=namespace["global_prefix"],
        global_cfg_file=namespace["global_cfg_file"],
        config_default=namespace["config_default"],
        config_compatibility=namespace["config_compatibility"],
        set_config_value=namespace["_set_config_value"],
        set_global_variables=namespace["set_global_variables"],
    ).initialize()
    _initialized_namespaces.add(id(namespace))


@dataclass(frozen=True)
class GlobalConfigRuntime:
    """Apply config defaults and merge Ortho4XP.cfg into runtime globals."""

    cfg_vars: dict[str, dict[str, Any]]
    cfg_global_tile_vars: dict[str, dict[str, Any]]
    cfg_app_vars: dict[str, dict[str, Any]]
    global_prefix: str
    global_cfg_file: str
    config_default: Callable[[dict[str, Any]], Any]
    config_compatibility: Callable[[Any], str]
    set_config_value: Callable[[str, Any], None]
    set_global_variables: Callable[[str, str], None]

    def initialize(self) -> None:
        """Apply defaults first, then overlay user/global config values."""
        self._initialize_default_config_values()
        self._load_or_create_global_config()

    def _initialize_default_config_values(self) -> None:
        """Populate every registered config variable with its default value."""
        for var in self.cfg_vars:
            self.set_config_value(var, self.config_default(self.cfg_vars[var]))

    def _load_or_create_global_config(self) -> None:
        """Read the global config file or create it when it is absent."""
        try:
            self._load_global_config()
        except FileNotFoundError:
            self._create_global_config()
        except OSError:
            UI.log_exception("Error accessing global config file")

    def _load_global_config(self) -> None:
        """Load active assignment lines from the global config file."""
        with open(self.global_cfg_file) as f:
            for line in f.readlines():
                self._load_global_config_line(line)

    def _load_global_config_line(self, line: str) -> None:
        """Apply one non-comment config line and report invalid values."""
        line = line.strip()
        if not line or line[0] == "#":
            return
        try:
            self._apply_global_config_line(line)
        except UnsupportedWaterTechError as exc:
            UI.lvprint(0, "Global config file contains an unsupported line:", line)
            UI.vprint(1, exc)
        except (KeyError, TypeError, ValueError, SyntaxError) as exc:
            UI.lvprint(1, "Global config file contains an invalid line:", line)
            UI.vprint(3, exc)

    def _apply_global_config_line(self, line: str) -> None:
        """Apply one value to both tile/app and global tile config namespaces."""
        var, value = line.split("=", 1)
        value = self.config_compatibility(value)
        self.set_global_variables(var, value)
        self.set_global_variables(self.global_prefix + var, value)

    def _create_global_config(self) -> None:
        """Create a missing global config file from registered defaults."""
        with open(self.global_cfg_file, "w") as file:
            self._write_default_global_tile_config(file)
            self._write_default_app_config(file)
        UI.log_event("No global config file found. New config created using defaults.")

    def _write_default_global_tile_config(self, file) -> None:
        """Write default tile config values without the global_ prefix."""
        for var, value in self.cfg_global_tile_vars.items():
            config_var = var.replace(self.global_prefix, "")
            file.write(config_var + "=" + str(value["default"]) + "\n")

    def _write_default_app_config(self, file) -> None:
        """Write default application config values."""
        for var, value in self.cfg_app_vars.items():
            file.write(var + "=" + str(value["default"]) + "\n")
