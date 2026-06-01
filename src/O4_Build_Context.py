from typing import Any

import O4_UI_Utils as UI


class BuildContext:
    """Typed facade over UI process-state globals.

    Build steps receive this instead of reading UI.* directly.
    Properties delegate to the UI module for bidirectional consistency.
    """

    @property
    def red_flag(self) -> bool:
        return UI.red_flag

    @red_flag.setter
    def red_flag(self, value: bool) -> None:
        UI.red_flag = value

    @property
    def is_working(self) -> bool:
        return UI.is_working

    @is_working.setter
    def is_working(self, value: bool) -> None:
        UI.is_working = value

    @property
    def verbosity(self) -> int:
        return UI.verbosity

    @verbosity.setter
    def verbosity(self, value: int) -> None:
        UI.verbosity = value

    @property
    def cleaning_level(self) -> int:
        return UI.cleaning_level

    @cleaning_level.setter
    def cleaning_level(self, value: int) -> None:
        UI.cleaning_level = value

    @property
    def gui(self) -> Any | None:
        return UI.gui

    @gui.setter
    def gui(self, value: Any | None) -> None:
        UI.gui = value

    def vprint(self, min_verbosity: int, *args: Any) -> None:
        UI.vprint(min_verbosity, *args)
