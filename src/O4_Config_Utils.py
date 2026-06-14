"""Ortho4XP configuration window."""

import ast
import os
import tkinter as tk
import tkinter.ttk as ttk
from math import ceil
from tkinter import E, N, S, W, filedialog, messagebox
from typing import Any, cast

import O4_Cfg_Vars as CFG
import O4_Config_Runtime as CONFIG_RUNTIME
import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_OSM_Utils as OSM
import O4_Overlay_Utils as OVL
import O4_Tile_Utils as TILE
import O4_UI_Utils as UI
import O4_Vector_Map as VMAP
from O4_Cfg_Vars import (
    cfg_app_vars,
    cfg_global_tile_vars,
    cfg_tile_vars,
    cfg_vars,
    global_prefix,
    gui_app_vars_long,
    gui_app_vars_short,
    list_app_vars,
    list_cfg_vars,
    list_dsf_vars,
    list_global_dsf_vars,
    list_global_mask_vars,
    list_global_mesh_vars,
    list_global_tile_vars,
    list_global_vector_vars,
    list_mask_vars,
    list_mesh_vars,
    list_tile_vars,
    list_vector_vars,
)
from O4_Config_Models import (
    UnsupportedWaterTechError,
    coerce_config_value,
    config_default,
    parse_legacy_config_literal,
    parse_legacy_zone_append,
    validate_config_registry,
)

cfg_app_vars = cast(dict[str, dict[str, Any]], cfg_app_vars)
cfg_tile_vars = cast(dict[str, dict[str, Any]], cfg_tile_vars)
cfg_global_tile_vars = cast(dict[str, dict[str, Any]], cfg_global_tile_vars)
cfg_vars = cast(dict[str, dict[str, Any]], cfg_vars)

global_cfg_file = FNAMES.resource_path("Ortho4XP.cfg")
global_cfg_bak_file = FNAMES.resource_path("Ortho4XP.cfg.bak")

validate_config_registry(cfg_vars)

custom_scenery_dir: str = config_default(cfg_app_vars["custom_scenery_dir"])
zone_list: list[Any] = config_default(cfg_tile_vars["zone_list"])


def _config_target(var: str):
    module_name = cast(str | None, cfg_vars[var].get("module"))
    if module_name:
        return globals()[module_name], var
    return globals(), var


def _get_config_value(var: str):
    target, name = _config_target(var)
    if isinstance(target, dict):
        return target[name]
    return getattr(target, name)


def _set_config_value(var: str, value) -> None:
    target, name = _config_target(var)
    if isinstance(target, dict):
        target[name] = value
    else:
        setattr(target, name, value)


def _coerce_config_value(var: str, value):
    return coerce_config_value(var, value, cfg_vars)


def _validate_loaded_config_value(var: str, value):
    _coerce_config_value(var, value)
    return value


def _report_unsupported_water_tech(error: UnsupportedWaterTechError) -> None:
    UI.lvprint(0, "CFG error:", error)


def _append_legacy_zone_line(line: str, zone_list: list[Any]) -> bool:
    if "zone_list.append" not in line:
        return False
    try:
        zone = parse_legacy_zone_append(line)
        if zone is not None and zone not in zone_list:
            zone_list.append(zone)
    except (TypeError, ValueError, SyntaxError) as exc:
        UI.vprint(3, exc)
    return True


def _active_config_lines(lines):
    for line in lines:
        line = line.strip()
        if line and line[0] != "#":
            yield line


def _loaded_config_value(line, ignored_vars, key_transform, legacy_zone_target):
    try:
        (var, value) = line.split("=", 1)
        if var in ignored_vars:
            return None
        var = key_transform(var)
        value = config_compatibility(value)
        _validate_loaded_config_value(var, value)
        return var, value
    except UnsupportedWaterTechError as exc:
        _report_unsupported_water_tech(exc)
        raise
    except (KeyError, TypeError, ValueError, SyntaxError) as exc:
        if legacy_zone_target is None or not _append_legacy_zone_line(
            line, legacy_zone_target
        ):
            UI.vprint(2, exc)
        return None


def _iter_loaded_config_values(
    lines,
    *,
    ignored_vars=(),
    key_transform=lambda var: var,
    legacy_zone_target: list[Any] | None = None,
):
    for line in _active_config_lines(lines):
        loaded_value = _loaded_config_value(
            line, ignored_vars, key_transform, legacy_zone_target
        )
        if loaded_value is not None:
            yield loaded_value


def _config_hint(registry: dict[str, dict[str, Any]], item: str) -> str:
    return str(registry[item]["hint"])


def _config_choice_values(registry: dict[str, dict[str, Any]], item: str) -> list[str]:
    if registry[item]["type"] == bool:
        return ["True", "False"]
    return [str(x) for x in cast(list[Any] | tuple[Any, ...], registry[item]["values"])]


def set_global_variables(var: str, value: str) -> None:
    """
    Set global Python variables for the application.

    :param str var: variable name
    :param str value: value for variable
    :returns: None
    """
    # There are no global_* variables for the app config settings so skip them
    if var.startswith(global_prefix):
        var_without_global = var[len(global_prefix) :]
        if var_without_global in cfg_app_vars:
            return
    _set_config_value(var, _coerce_config_value(var, value))


def config_compatibility(value) -> str:
    """
    Check for compatibility with config files from version <= 1.20.

    :param str value: value to check
    :returns: value in format based on cfg_vars
    :return type: str
    """
    return parse_legacy_config_literal(value)


def initialize_global_config(*, force: bool = False) -> None:
    """Initialize process-wide config values from defaults and Ortho4XP.cfg."""
    CONFIG_RUNTIME.initialize_from_namespace(globals(), force=force)


################################################################################
# Runtime initialization to default values
# Some variables are set using simply their name
# Others are set using the module name and the variable name because
# they are defined in a different module and overriden when the config is loaded (below)
# hence runtime entry points call initialize_global_config() before using Tile.


################################################################################
class Tile:
    """Class for building tiles."""

    def __init__(self, lat, lon, custom_build_dir):
        initialize_global_config()

        self.lat = lat
        self.lon = lon
        self.custom_build_dir = custom_build_dir
        self.grouped = bool(
            custom_build_dir and not custom_build_dir.endswith(("/", "\\"))
        )
        self.build_dir = FNAMES.build_dir(lat, lon, custom_build_dir)
        self.dem = None
        self.default_website = globals()["default_website"]
        self.default_zl = globals()["default_zl"]
        self.water_tech = globals()["water_tech"]
        self.zone_list = globals()["zone_list"]
        for var in list_tile_vars:
            setattr(self, var, globals()[var])

    def make_dirs(self):
        if os.path.isdir(self.build_dir):
            if not os.access(self.build_dir, os.W_OK):
                UI.vprint(
                    0,
                    "OS error: Tile directory",
                    self.build_dir,
                    " is write protected.",
                )
                raise Exception
        else:
            try:
                os.makedirs(self.build_dir)
            except OSError as exc:
                UI.vprint(
                    0,
                    "OS error: Cannot create tile directory",
                    self.build_dir,
                    " check file permissions.",
                )
                UI.vprint(3, exc)
                raise Exception from exc

    def read_from_config(self, config_file=None, use_global=False):
        """
        Read tile config from config file and update class variables.

        :params str config_file: path to config file; unknown use case
        :params bool use_global: force use of global config file

        :returns: 1 if successful, 0 if not
        :return type: int
        """
        if not config_file:
            config_file = os.path.join(
                self.build_dir,
                "Ortho4XP_" + FNAMES.short_latlon(self.lat, self.lon) + ".cfg",
            )
            if not os.path.isfile(config_file) or use_global:
                config_file = global_cfg_file

                if not os.path.isfile(config_file):
                    UI.lvprint(
                        0,
                        "CFG error: No tile or global config file found.",
                        FNAMES.short_latlon(self.lat, self.lon),
                    )
                    return 0
        try:
            with open(config_file) as f:
                for var, value in _iter_loaded_config_values(
                    f, legacy_zone_target=self.zone_list
                ):
                    setattr(self, var, _coerce_config_value(var, value))
            return 1
        except UnsupportedWaterTechError:
            return 0
        except OSError as exc:
            UI.lvprint(
                0,
                "CFG error: Could not read config file for tile",
                FNAMES.short_latlon(self.lat, self.lon),
            )
            UI.vprint(3, exc)
            return 0

    def write_to_config(self, config_file=None):
        """
        Create tile config file from class variables.

        :params str config_file: path to config file; unknown use case

        :returns: 1 if successful, 0 if not
        :return type: int
        """
        if not config_file:
            config_file = os.path.join(
                self.build_dir,
                "Ortho4XP_" + FNAMES.short_latlon(self.lat, self.lon) + ".cfg",
            )
            config_file_bak = config_file + ".bak"
        try:
            os.replace(config_file, config_file_bak)
        except OSError as exc:
            UI.vprint(3, exc)
        try:
            with open(config_file, "w") as f:
                for var in list_tile_vars:
                    tile_zones = []
                    lat = self.lat
                    lon = self.lon
                    if lat < 0:
                        lat = lat + 1
                    if lon < 0:
                        lon = lon + 1
                    for zone in globals()["zone_list"]:
                        _zone_list = [int(coord) for coord in zone[0]]
                        _zone_list = set(_zone_list)
                        if lat in _zone_list and lon in _zone_list:
                            tile_zones.append(zone)
                            _log_zones_in_tile(tile_zones)
                    if var == "zone_list":
                        f.write(var + "=" + str(tile_zones) + "\n")
                    else:
                        f.write(var + "=" + str(getattr(self, var)) + "\n")
            return 1
        except OSError as e:
            UI.vprint(2, e)
            UI.lvprint(
                0,
                "CFG error: Could not write config file for tile",
                FNAMES.short_latlon(self.lat, self.lon),
            )
            return 0


################################################################################


################################################################################
class Ortho4XP_Config(tk.Toplevel):
    """Ortho4XP configuration window."""

    def __init__(self, parent):

        tk.Toplevel.__init__(self)
        self.option_add("*Font", "TkFixedFont")
        self.title("Ortho4XP Config")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        if self.winfo_screenheight() >= 1024:
            self.pady = 5
        else:
            self.pady = 1

        self.folder_icon = tk.PhotoImage(
            file=os.path.join(FNAMES.Utils_dir, "Folder.gif")
        )
        # Ortho4XP main window reference
        self.parent = parent

        # Catch window close using operating system close button
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        # Create a notebook which provides a tabbed interface
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky=N + S + W + E)
        # Fixes issue where sometimes tab content is not displayed until mouse is moved
        self.notebook.bind(
            "<<NotebookTabChanged>>", lambda event: self.update_idletasks()
        )

        # Create frames for each tab
        self.tile_config_frame = tk.Frame(self.notebook, bg="light green")
        self.global_config_frame = tk.Frame(self.notebook, bg="light green")
        self.app_config_frame = tk.Frame(self.notebook, bg="light green")

        # Add frames to the notebook
        self.notebook.add(self.tile_config_frame, text="Tile Config")
        self.notebook.add(self.global_config_frame, text="Global Config")
        self.notebook.add(self.app_config_frame, text="Application Config")

        # Initialize Tkinter objects
        self.v_ = {}
        for item in cfg_vars:
            self.v_[item] = tk.StringVar()

        self.tile_cfg_msg = tk.StringVar()

        # Set values for Tkinter objects for GUI display
        self.v_["default_website"] = self.parent.default_website
        self.v_["default_zl"] = self.parent.default_zl
        self.load_interface_from_variables()

        # Initialize content for each tab
        self.tile_config(self.tile_config_frame)
        self.global_config(self.global_config_frame)
        self.app_config(self.app_config_frame)

        self.tile_cfg_status()

    def tile_cfg_status(self, *args) -> None:
        """Update the tile configuration status message and widget states."""
        if self.parent.tile_cfg_exists.get():
            self.tile_cfg_msg.set(
                f"Tile configuration loaded for "
                f"{self.parent.lat.get()} {self.parent.lon.get()}"
            )
            state = "normal"
            for _, value in self.tile_entry_.items():
                value.config(state=state)

            self.btn_tile_dem.config(state=state)
            self.btn_reset_tile_cfg.config(state=state)
            self.btn_restore_tile_cfg.config(state=state)
            self.btn_load_tile_cfg.config(state=state)
            self.btn_write_tile_cfg.config(state=state)
        else:
            self.tile_cfg_msg.set(
                f"No tile configuration for "
                f"{self.parent.lat.get()}{self.parent.lon.get()}. "
                f"Using global configuration settings."
            )
            state = "disabled"
            for _, value in self.tile_entry_.items():
                value.config(state=state)

            self.btn_tile_dem.config(state=state)
            self.btn_reset_tile_cfg.config(state=state)
            self.btn_restore_tile_cfg.config(state=state)
            self.btn_load_tile_cfg.config(state=state)

    def tile_config(self, frame: tk.Frame) -> None:
        """Tile configuration section."""
        # Allow base frame to expand with window resize
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        main_frame = tk.Frame(frame, border=4, bg="light green")
        frame_status = tk.Frame(main_frame, border=0, padx=5, pady=0, bg="light green")
        frame_cfg = tk.Frame(main_frame, border=0, padx=5, pady=0, bg="light green")
        frame_dem = tk.Frame(
            frame_cfg, border=0, padx=0, pady=self.pady, bg="light green"
        )
        frame_lastbtn = tk.Frame(
            main_frame, border=0, padx=5, pady=self.pady, bg="light green"
        )
        # Allow widgets to shrink and expand with window resize
        frame_status.columnconfigure(0, weight=0)
        frame_status.rowconfigure(0, weight=0)
        for j in range(8):
            frame_cfg.columnconfigure(j, weight=1)

        frame_cfg.rowconfigure(0, weight=1)

        for j in range(6):
            frame_lastbtn.columnconfigure(j, weight=1)

        frame_lastbtn.rowconfigure(0, weight=1)

        main_frame.grid(row=0, column=0, sticky=N + S + W + E)
        frame_status.grid(row=0, column=0, pady=10, sticky=N + S + E + W)
        frame_cfg.grid(row=1, column=0, pady=10, sticky=N + S + E + W)
        frame_lastbtn.grid(row=2, column=0, pady=10, sticky=S + E + W)
        # Add a row with weight 1 to push frame_lastbtn to the bottom with window resize
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)
        main_frame.columnconfigure(0, weight=1)

        self.tile_entry_ = {}

        col = 0
        next_row = 0

        tk.Label(
            frame_status,
            textvariable=self.tile_cfg_msg,
            bg="light green",
            fg="black",
            font="TKFixedFont 15",
        ).grid(row=0, column=0, pady=0, sticky=N + S + W + E)

        for title, sub_list in (
            ("Vector data", list_vector_vars),
            ("Mesh", list_mesh_vars),
            ("Masks", list_mask_vars),
            ("DSF/Imagery", list_dsf_vars),
        ):
            tk.Label(
                frame_cfg,
                text=title,
                bg="light green",
                anchor=W,
                font="TKFixedFont 15",
            ).grid(
                row=1,
                column=col,
                columnspan=2,
                pady=(0, 10),
                sticky=N + S + E + W,
            )
            row = 2
            for item in sub_list:
                text = str(cfg_tile_vars[item].get("short_name", item))
                ttk.Button(
                    frame_cfg,
                    text=text,
                    takefocus=False,
                    command=lambda item=item: self.popup(
                        item, _config_hint(cfg_tile_vars, item)
                    ),
                ).grid(row=row, column=col, padx=2, pady=2, sticky=E + W + N + S)
                if (
                    cfg_tile_vars[item]["type"] == bool
                    or "values" in cfg_tile_vars[item]
                ):
                    values = _config_choice_values(cfg_tile_vars, item)
                    self.tile_entry_[item] = ttk.Combobox(
                        frame_cfg,
                        values=values,
                        textvariable=self.v_[item],
                        width=6,
                        state="readonly",
                        style="O4.TCombobox",
                    )
                else:
                    self.tile_entry_[item] = ttk.Entry(
                        frame_cfg, textvariable=self.v_[item], width=7
                    )
                self.tile_entry_[item].grid(
                    row=row,
                    column=col + 1,
                    padx=(0, 20),
                    pady=2,
                    sticky=N + S + W,
                )
                row += 1
            next_row = max(next_row, row)
            col += 2
        row = next_row

        frame_dem.grid(row=row, column=0, columnspan=6, sticky=N + S + W + E)

        item = "custom_dem"

        ttk.Button(
            frame_dem,
            text=item,
            takefocus=False,
            command=lambda item=item: self.popup(
                item, _config_hint(cfg_tile_vars, item)
            ),
        ).grid(row=0, column=0, padx=2, pady=2, sticky=E + W)

        values = DEM.available_sources[1::2]

        self.tile_entry_[item] = ttk.Combobox(
            frame_dem,
            values=values,
            textvariable=self.v_[item],
            width=80,
            style="O4.TCombobox",
        )
        self.tile_entry_[item].grid(
            row=0, column=1, padx=(2, 0), pady=8, sticky=N + S + W + E
        )

        self.btn_tile_dem = ttk.Button(
            frame_dem,
            image=self.folder_icon,
            command=lambda: self.choose_dem(),
            style="Flat.TButton",
        )
        self.btn_tile_dem.grid(row=0, column=2, padx=2, pady=0, sticky=W)
        self.btn_tile_dem.bind("<Shift-ButtonPress-1>", lambda event: self.add_dem())

        item = "fill_nodata"

        ttk.Button(
            frame_cfg,
            text=item,
            takefocus=False,
            command=lambda item=item: self.popup(
                item, _config_hint(cfg_tile_vars, item)
            ),
        ).grid(row=row, column=6, padx=2, pady=2, sticky=E + W)

        values = ["True", "False"]

        self.tile_entry_[item] = ttk.Combobox(
            frame_cfg,
            values=values,
            textvariable=self.v_[item],
            width=6,
            state="readonly",
            style="O4.TCombobox",
        )
        self.tile_entry_[item].grid(row=row, column=7, padx=2, pady=2, sticky=W)
        row += 1

        # Bottom row buttons
        self.btn_reset_tile_cfg = ttk.Button(
            frame_lastbtn,
            text="Reset to Global",
            command=self.reset_tile_cfg,
        )
        self.btn_reset_tile_cfg.grid(
            row=0, column=1, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_restore_tile_cfg = ttk.Button(
            frame_lastbtn,
            text="Load Backup Cfg",
            command=self.load_backup_tile_cfg,
        )
        self.btn_restore_tile_cfg.grid(
            row=0, column=2, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_load_tile_cfg = ttk.Button(
            frame_lastbtn,
            text="Load Tile Cfg ",
            command=self.load_tile_cfg,
        )
        self.btn_load_tile_cfg.grid(
            row=0, column=3, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_write_tile_cfg = ttk.Button(
            frame_lastbtn,
            text="Save Tile Config",
            command=self.write_tile_cfg,
        )
        self.btn_write_tile_cfg.grid(
            row=0, column=4, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_exit = ttk.Button(
            frame_lastbtn, text="Exit", command=self.close_window
        )
        self.btn_exit.grid(
            row=0, column=5, padx=5, pady=self.pady, sticky=N + S + E + W
        )

    def global_config(self, frame: tk.Frame) -> None:
        """Global tile configuration frame."""
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        main_frame = tk.Frame(frame, border=4, bg="light green")
        frame_cfg = tk.Frame(
            main_frame, border=0, padx=5, pady=self.pady, bg="light green"
        )
        frame_dem = tk.Frame(
            frame_cfg, border=0, padx=0, pady=self.pady, bg="light green"
        )
        frame_lastbtn = tk.Frame(
            main_frame, border=0, padx=5, pady=self.pady, bg="light green"
        )

        for j in range(8):
            frame_cfg.columnconfigure(j, weight=1)

        frame_cfg.rowconfigure(0, weight=1)

        for j in range(6):
            frame_lastbtn.columnconfigure(j, weight=1)

        frame_lastbtn.rowconfigure(0, weight=1)

        main_frame.grid(row=0, column=0, sticky=N + S + W + E)
        frame_cfg.grid(row=0, column=0, pady=10, sticky=N + S + E + W)
        frame_lastbtn.grid(row=1, column=0, pady=10, sticky=S + E + W)

        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)
        main_frame.columnconfigure(0, weight=1)

        self.global_entry_ = {}

        col = 0
        next_row = 0

        for title, sub_list in (
            ("Vector data", list_global_vector_vars),
            ("Mesh", list_global_mesh_vars),
            ("Masks", list_global_mask_vars),
            ("DSF/Imagery", list_global_dsf_vars),
        ):
            tk.Label(
                frame_cfg,
                text=title,
                bg="light green",
                anchor=W,
                font="TKFixedFont 15",
            ).grid(
                row=0,
                column=col,
                columnspan=2,
                pady=(0, 10),
                sticky=N + S + E + W,
            )
            row = 1
            for item in sub_list:
                text = str(cfg_global_tile_vars[item].get("short_name", item))
                text = text.replace(global_prefix, "")
                ttk.Button(
                    frame_cfg,
                    text=text,
                    takefocus=False,
                    command=lambda item=item: self.popup(
                        item, _config_hint(cfg_global_tile_vars, item)
                    ),
                ).grid(row=row, column=col, padx=2, pady=2, sticky=E + W + N + S)
                if (
                    cfg_global_tile_vars[item]["type"] == bool
                    or "values" in cfg_global_tile_vars[item]
                ):
                    values = _config_choice_values(cfg_global_tile_vars, item)
                    self.global_entry_[item] = ttk.Combobox(
                        frame_cfg,
                        values=values,
                        textvariable=self.v_[item],
                        width=6,
                        state="readonly",
                        style="O4.TCombobox",
                    )
                else:
                    self.global_entry_[item] = ttk.Entry(
                        frame_cfg, textvariable=self.v_[item], width=7
                    )
                self.global_entry_[item].grid(
                    row=row,
                    column=col + 1,
                    padx=(0, 20),
                    pady=2,
                    sticky=N + S + W,
                )
                row += 1
            next_row = max(next_row, row)
            col += 2

        row = next_row

        frame_dem.grid(row=row, column=0, columnspan=6, sticky=N + S + W + E)

        text = "custom_dem"
        item = "global_custom_dem"

        ttk.Button(
            frame_dem,
            text=text,
            takefocus=False,
            command=lambda item=item: self.popup(
                item, _config_hint(cfg_global_tile_vars, item)
            ),
        ).grid(row=0, column=0, padx=2, pady=2, sticky=E + W)

        values = DEM.available_sources[1::2]
        self.global_entry_[item] = ttk.Combobox(
            frame_dem,
            values=values,
            textvariable=self.v_[item],
            width=80,
            style="O4.TCombobox",
        )
        self.global_entry_[item].grid(
            row=0, column=1, padx=(2, 0), pady=8, sticky=N + S + W + E
        )

        self.btn_global_dem = ttk.Button(
            frame_dem,
            image=self.folder_icon,
            command=lambda: self.choose_dem(global_config=True),
            style="Flat.TButton",
        )
        self.btn_global_dem.grid(row=0, column=2, padx=2, pady=0, sticky=W)
        self.btn_global_dem.bind(
            "<Shift-ButtonPress-1>", lambda event: self.add_dem(global_config=True)
        )

        text = "fill_nodata"
        item = "global_fill_nodata"

        ttk.Button(
            frame_cfg,
            text=text,
            takefocus=False,
            command=lambda item=item: self.popup(
                item, _config_hint(cfg_global_tile_vars, item)
            ),
        ).grid(row=row, column=6, padx=2, pady=2, sticky=E + W)

        values = ["True", "False"]

        self.global_entry_[item] = ttk.Combobox(
            frame_cfg,
            values=values,
            textvariable=self.v_[item],
            width=6,
            state="readonly",
            style="O4.TCombobox",
        )
        self.global_entry_[item].grid(row=row, column=7, padx=2, pady=2, sticky=W)
        row += 1

        # Bottom row buttons
        self.btn_reset_global_cfg = ttk.Button(
            frame_lastbtn,
            text="Reset to Defaults",
            command=self.reset_global_cfg,
        )
        self.btn_reset_global_cfg.grid(
            row=0, column=2, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_load_backup_global_tile_cfg = ttk.Button(
            frame_lastbtn,
            text="Load Backup Cfg",
            command=self.load_backup_global_tile_cfg,
        )
        self.btn_load_backup_global_tile_cfg.grid(
            row=0, column=3, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_save_global_cfg = ttk.Button(
            frame_lastbtn,
            text="Save Global Config",
            command=self.write_global_cfg,
        )
        self.btn_save_global_cfg.grid(
            row=0, column=4, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_exit = ttk.Button(
            frame_lastbtn, text="Exit", command=self.close_window
        )
        self.btn_exit.grid(
            row=0, column=5, padx=5, pady=self.pady, sticky=N + S + E + W
        )

    def app_config(self, frame: tk.Frame) -> None:
        """Application configuration frame."""
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        main_frame = tk.Frame(frame, border=4, bg="light green")
        frame_cfg = tk.Frame(
            main_frame, border=0, padx=5, pady=self.pady, bg="light green"
        )
        frame_lastbtn = tk.Frame(
            main_frame, border=0, padx=5, pady=self.pady, bg="light green"
        )

        for j in range(8):
            frame_cfg.columnconfigure(j, weight=1)

        frame_cfg.rowconfigure(0, weight=1)

        for j in range(6):
            frame_lastbtn.columnconfigure(j, weight=1)

        frame_lastbtn.rowconfigure(0, weight=1)

        main_frame.grid(row=0, column=0, sticky=N + S + W + E)
        frame_cfg.grid(row=0, column=0, pady=10, sticky=N + S + E + W)
        frame_lastbtn.grid(row=1, column=0, pady=10, sticky=S + E + W)

        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)
        main_frame.columnconfigure(0, weight=1)

        self.app_entry_ = {}

        row = 2
        col = 0

        l = ceil((len(gui_app_vars_short)) / 4)
        this_row = row
        for j, item in enumerate(gui_app_vars_short):
            col = 2 * (j // l)
            row = this_row + j % l
            text = str(cfg_app_vars[item].get("short_name", item))
            ttk.Button(
                frame_cfg,
                text=text,
                takefocus=False,
                command=lambda item=item: self.popup(
                    item, _config_hint(cfg_app_vars, item)
                ),
            ).grid(row=row, column=col, padx=2, pady=2, sticky=E + W + N + S)
            if cfg_app_vars[item]["type"] == bool or "values" in cfg_app_vars[item]:
                values = (
                    ["True", "False"]
                    if cfg_app_vars[item]["type"] == bool
                    else _config_choice_values(cfg_app_vars, item)
                )
                self.app_entry_[item] = ttk.Combobox(
                    frame_cfg,
                    values=values,
                    textvariable=self.v_[item],
                    width=6,
                    state="readonly",
                    style="O4.TCombobox",
                )
            else:
                self.app_entry_[item] = tk.Entry(
                    frame_cfg,
                    textvariable=self.v_[item],
                    width=7,
                    bg="white",
                    fg="blue",
                )
            self.app_entry_[item].grid(
                row=row, column=col + 1, padx=(0, 20), pady=2, sticky=N + S + W
            )

        row = this_row + l

        for item in gui_app_vars_long:
            ttk.Button(
                frame_cfg,
                text=item,
                takefocus=False,
                command=lambda item=item: self.popup(
                    item, _config_hint(cfg_vars, item)
                ),
            ).grid(row=row, column=0, padx=2, pady=2, sticky=E + W + N + S)

            self.app_entry_[item] = tk.Entry(
                frame_cfg,
                textvariable=self.v_[item],
                bg="white",
                fg="blue",
            )
            self.app_entry_[item].grid(
                row=row,
                column=1,
                columnspan=5,
                padx=(2, 0),
                pady=2,
                sticky=N + S + E + W,
            )

            ttk.Button(
                frame_cfg,
                image=self.folder_icon,
                command=lambda item=item: self.choose_dir(item),
                style="Flat.TButton",
            ).grid(row=row, column=6, padx=2, pady=0, sticky=N + S + W)
            row += 1

        # Bottom row buttons
        self.btn_reload_app_cfg = ttk.Button(
            frame_lastbtn,
            text="Reset to Defaults",
            command=self.reset_app_cfg,
        )
        self.btn_reload_app_cfg.grid(
            row=0, column=2, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_load_backup_app_cfg = ttk.Button(
            frame_lastbtn,
            text="Load Backup Cfg",
            command=self.load_backup_app_cfg,
        )
        self.btn_load_backup_app_cfg.grid(
            row=0, column=3, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_save_app_cfg = ttk.Button(
            frame_lastbtn,
            text="Save App Config",
            command=self.write_app_cfg,
        )
        self.btn_save_app_cfg.grid(
            row=0, column=4, padx=5, pady=self.pady, sticky=N + S + E + W
        )

        self.btn_exit = ttk.Button(
            frame_lastbtn, text="Exit", command=self.close_window
        )
        self.btn_exit.grid(
            row=0, column=5, padx=5, pady=self.pady, sticky=N + S + E + W
        )

    def load_interface_from_variables(self) -> None:
        """Load the configuration interface values for all tabs."""
        for var in list_cfg_vars:
            self.v_[var].set(str(_get_config_value(var)))

    def reset_tile_cfg(self) -> int | None:
        """Reset tile settings to global tile settings."""
        try:
            (lat, lon) = self.parent.get_lat_lon()
        except (TypeError, ValueError):
            return 0
        # Find all the zones for the active tile
        tile_zones = []
        if lat < 0:
            lat = lat + 1
        if lon < 0:
            lon = lon + 1
        for zone in globals()["zone_list"]:
            _zone_list = [int(coord) for coord in zone[0]]
            _zone_list = set(_zone_list)
            if lat in _zone_list and lon in _zone_list:
                tile_zones.append(zone)
        if tile_zones:
            response = messagebox.askyesnocancel(
                "Confirmation", "Save tile zones?", parent=self
            )
            if response is None:
                return
            # Remove the current tile zones from global zone_list
            if response is False:
                # Only remove the active tiles from the global zone_list
                globals()["zone_list"] = [
                    zone for zone in globals()["zone_list"] if zone not in tile_zones
                ]
        for var in list_tile_vars:
            # Skip zone_list in list_tile_vars since zone_list is not in global config
            if var == "zone_list":
                continue
            # default_website is not stored in global config
            if var == "default_website":
                self.v_["zone_list"].set(self.parent.default_website.get())
                continue
            # default_zl is not stored in global config
            if var == "default_zl":
                self.v_["zone_list"].set(self.parent.default_zl.get())
                continue
            # Since we're looping through list_tile_vars, we need to prefix the key for getting
            # the value from the global config tab
            _global_var = global_prefix + var
            self.v_[var].set(self.v_[_global_var].get())
        UI.vprint(1, "Tile settings reset to global tile settings.")

    def load_backup_tile_cfg(self) -> int | None:
        """Load backup tile configuration settings."""
        zone_list = []
        try:
            (lat, lon) = self.parent.get_lat_lon()
        except (TypeError, ValueError):
            return 0
        custom_build_dir = self.parent.custom_build_dir_entry.get()
        build_dir = FNAMES.build_dir(lat, lon, custom_build_dir)
        try:
            with open(
                os.path.join(
                    build_dir,
                    "Ortho4XP_" + FNAMES.short_latlon(lat, lon) + ".cfg.bak",
                ),
            ) as f:
                try:
                    for var, value in _iter_loaded_config_values(
                        f, legacy_zone_target=zone_list
                    ):
                        self.v_[var].set(value)
                except UnsupportedWaterTechError:
                    return 0
        except FileNotFoundError:
            messagebox.showinfo("Not found", "No backup tile configuration found.")
            return
        if zone_list and not self.v_["zone_list"].get():
            self.v_["zone_list"].set(str(zone_list))
        # Apply changes to update global variables
        self.apply_changes("tile")
        UI.vprint(0, f"Backup configuration loaded for tile at {lat} {lon}")

    def load_tile_cfg(self) -> int | None:
        """Load tile configuration settings for active tile."""
        zone_list = []
        try:
            (lat, lon) = self.parent.get_lat_lon()
        except (TypeError, ValueError):
            return 0
        custom_build_dir = self.parent.custom_build_dir_entry.get()
        build_dir = FNAMES.build_dir(lat, lon, custom_build_dir)
        config_path = os.path.join(
            build_dir,
            "Ortho4XP_" + FNAMES.short_latlon(lat, lon) + ".cfg",
        )
        fallback_config_path = os.path.join(build_dir, "Ortho4XP.cfg")
        if not os.path.isfile(config_path):
            config_path = fallback_config_path
        try:
            with open(config_path) as f:
                try:
                    for var, value in _iter_loaded_config_values(
                        f, legacy_zone_target=zone_list
                    ):
                        self.v_[var].set(value)
                except UnsupportedWaterTechError:
                    return 0
        except OSError:
            messagebox.showinfo("Not found", "No tile configuration found.")
            return 0
        if not self.v_["zone_list"].get():
            self.v_["zone_list"].set(str(zone_list))
        self.parent.tile_cfg_exists.set(True)
        # Apply changes to update global variables
        self.apply_changes("tile")
        UI.vprint(0, f"Configuration loaded for tile at {lat} {lon}")

    def write_tile_cfg(self) -> int | None:
        """Save tile configuration settings for active tile."""
        try:
            (lat, lon) = self.parent.get_lat_lon()
        except (TypeError, ValueError):
            return 0
        custom_build_dir = self.parent.custom_build_dir_entry.get()
        build_dir = FNAMES.build_dir(lat, lon, custom_build_dir)
        tile_cfg_file = os.path.join(
            build_dir, "Ortho4XP_" + FNAMES.short_latlon(lat, lon) + ".cfg"
        )
        try:
            os.makedirs(build_dir, exist_ok=True)
        except OSError:
            self.popup("ERROR", "Cannot write into " + str(build_dir))
            return 0
        # Make a backup of the existing tile config file
        if os.path.isfile(tile_cfg_file):
            tile_cfg_file_bak = tile_cfg_file + ".bak"
            try:
                os.replace(tile_cfg_file, tile_cfg_file_bak)
            except OSError as exc:
                UI.vprint(3, exc)
        with open(tile_cfg_file, "w") as f:
            # Required for when the config window is left open to make sure
            # we retain any zone modifications
            self.v_["zone_list"].set(str(globals()["zone_list"]))
            # Apply changes to update global variables
            self.apply_changes("tile")
            # Get zones only for the tile
            tile_zones = []
            if lat < 0:
                lat = lat + 1
            if lon < 0:
                lon = lon + 1
            for zone in globals()["zone_list"]:
                _zone_list = [int(coord) for coord in zone[0]]
                _zone_list = set(_zone_list)
                if lat in _zone_list and lon in _zone_list:
                    tile_zones.append(zone)
                    _log_zones_saved_for_tile(lat, lon, tile_zones)
            for var in list_tile_vars:
                if var == "zone_list":
                    f.write(var + "=" + str(tile_zones) + "\n")
                else:
                    f.write(var + "=" + self.v_[var].get() + "\n")
        self.load_tile_cfg()
        self.tile_cfg_status()
        UI.vprint(
            1,
            f"Configuration saved for tile at {self.parent.lat.get()} {self.parent.lon.get()}",
        )
        return

    def reset_global_cfg(self) -> None:
        """Reset global tile settings to defaults."""
        # This does not reset the default_website and default_zl
        for var in cfg_global_tile_vars:
            # Update GUI Tkinter objects
            self.v_[var].set(str(cfg_global_tile_vars[var]["default"]))

        UI.vprint(1, "Global tile settings reset to defaults.")

    def load_backup_global_tile_cfg(self) -> None:
        """Load backup global tile configuration settings."""
        try:
            with open(global_cfg_bak_file) as f:
                for var, value in _iter_loaded_config_values(
                    f,
                    ignored_vars=list_app_vars,
                    key_transform=lambda var: global_prefix + var,
                ):
                    self.v_[var].set(value)
                # Apply changes to update global variables
                self.apply_changes("tile")
                UI.vprint(0, f"Backup configuration loaded for global tile settings.")
        except UnsupportedWaterTechError:
            return
        except FileNotFoundError:
            messagebox.showinfo("Not found", "No backup global configuration found.")
            return

    def write_global_cfg(self):
        """Write global configuration settings to Ortho4XP.cfg."""
        self.apply_changes("global")
        try:
            # Make a copy of the existing global config file
            if os.path.exists(global_cfg_file):
                os.replace(global_cfg_file, global_cfg_bak_file)
            # Get current GUI global tile settings as a dict
            # Remove global prefix since the cfg file doesn't use it
            current_config = {
                var.replace(global_prefix, ""): self.v_[var].get()
                for var in list_global_tile_vars
            }
            # Get current GUI app settings and add to the dict
            current_config.update({var: self.v_[var].get() for var in list_app_vars})
            # Get settings in existing config file returned as a dict
            config_file = self.cfg_to_dict(global_cfg_bak_file)
            # Update existing file with current app settings
            config_file.update(current_config)
            # Write to new configuration file
            with open(global_cfg_file, "w") as file:
                for key, value in config_file.items():
                    file.write(f"{key}={value}\n")
            # Load the tile config since it now exists
            if not self.parent.tile_cfg_exists.get():
                self.parent.load_tile_cfg(
                    int(self.parent.lat.get()), int(self.parent.lon.get())
                )
            UI.vprint(1, "Global tile configuration settings saved.")
        except OSError:
            UI.lvprint(1, "Could not write global config.")
            UI.log_exception("Could not write global config")
        return

    def reset_app_cfg(self) -> None:
        """Reset app settings to defaults."""
        for var in cfg_app_vars:
            # Update GUI Tkinter objects
            self.v_[var].set(str(cfg_app_vars[var]["default"]))
        UI.vprint(1, "Application settings reset to defaults.")

    def load_backup_app_cfg(self) -> None:
        """Load backup app configuration settings."""
        try:
            with open(global_cfg_bak_file) as f:
                for line in f.readlines():
                    line = line.strip()
                    if not line or line[0] == "#":
                        continue
                    (var, value) = line.split("=")
                    # Ignore global tile vars
                    if var in list_global_tile_vars:
                        continue
                    value = config_compatibility(value)
                    self.v_[var].set(value)
                # Apply changes to update global variables
                self.apply_changes("tile")
                UI.vprint(0, f"Backup configuration loaded for application settings.")
        except FileNotFoundError:
            messagebox.showinfo(
                "Not found", "No backup application configuration found."
            )
            return

    def write_app_cfg(self) -> None:
        """Save application settings to global configuration."""
        # Apply changes first to update global variables
        self.apply_changes("app")

        current_config = {}
        config_file = {}

        # Get current app settings and add to dict
        for var in list_app_vars:
            current_config[var] = self.v_[var].get()
        try:
            if os.path.exists(global_cfg_file):
                # Make a backup of the existing global config file
                os.replace(global_cfg_file, global_cfg_bak_file)
                # Get settings in existing config file returned as a dict
                config_file = self.cfg_to_dict(global_cfg_bak_file)
                # Update existing file with current app settings
                config_file.update(current_config)
                # Write to new configuration file
                self.dict_to_cfg(global_cfg_file, config_file)
            else:
                self.dict_to_cfg(global_cfg_file, current_config)

            UI.vprint(1, "Application configuration settings saved.")
        except OSError:
            UI.lvprint(1, "Could not write application settings to global config.")
            UI.log_exception("Could not write application settings to global config")
        return

    def apply_changes(self, tab: str) -> None:
        """
        Apply changes to update global variables.

        :param str tab: "tile", "global" or "app" for each tab
        :return: None
        """
        errors = []

        if tab == "global":
            for var in list_global_tile_vars:
                try:
                    globals()[var] = coerce_config_value(
                        var, self.v_[var].get(), cfg_global_tile_vars
                    )
                except (KeyError, TypeError, ValueError):
                    globals()[var] = config_default(cfg_global_tile_vars[var])
                    errors.append(var)
            if errors:
                error_text = (
                    "The following variables had wrong type\nand were reset "
                    + "to their default value!\n\n* "
                    + "\n* ".join(errors)
                )
                self.popup("ERROR", error_text)
        else:
            if tab == "tile":
                list_vars = list_tile_vars
                # Make sure existing zones in global zone_list are retained
                # and check for any duplicates before adding new zones
                for zone in ast.literal_eval(self.v_["zone_list"].get()):
                    if zone not in globals()["zone_list"]:
                        globals()["zone_list"].append(zone)
            if tab == "app":
                list_vars = list_app_vars
            for var in list_vars:
                # We don't want to update the global zone_list here
                # since it's already been updated by the save_zone_list in O4_GUI_Utils.py
                # and also by the code above
                if var == "zone_list":
                    continue
                try:
                    _set_config_value(
                        var, _coerce_config_value(var, self.v_[var].get())
                    )
                except (KeyError, TypeError, ValueError):
                    _set_config_value(var, config_default(cfg_vars[var]))
                    if tab == "app":
                        self.v_[var].set(str(cfg_vars[var]["default"]))
                    errors.append(var)
            if errors:
                error_text = (
                    "The following variables had wrong type\nand were reset "
                    + "to their default value!\n\n* "
                    + "\n* ".join(errors)
                )
                self.popup("ERROR", error_text)

    def check_unsaved_changes(self, select_tile=False) -> str | None:
        """
        Check for unsaved changes and prompt user to save.

        :param bool select_tile: Used with select_tile method in O4_OrthoXP_Earth_Preview class
        :return: Only returns "cancel" if user cancels the save prompt
        :rtype: str
        """
        try:
            (lat, lon) = self.parent.get_lat_lon()
        except (TypeError, ValueError):
            UI.log_exception("Could not get lat/lon coordinates")
            return

        custom_build_dir = self.parent.custom_build_dir_entry.get()
        build_dir = FNAMES.build_dir(lat, lon, custom_build_dir)

        unsaved_changes = {"tile": False, "global": False, "application": False}
        # Check Tile Config tab values against values in the tile config file
        try:
            with open(
                os.path.join(
                    build_dir, "Ortho4XP_" + FNAMES.short_latlon(lat, lon) + ".cfg"
                ),
            ) as f:
                file_dict = dict(line.strip().split("=") for line in f if line.strip())
                for var in list_tile_vars:
                    # Skip default_website and default_zl since they're not a part of the tab settings
                    if var == "default_website" or var == "default_zl":
                        continue
                    # Skip zone_list since we're only checking config tab values and default_website + default_zl
                    if var == "zone_list":
                        continue
                    tab_value = self.set_value_type(var, self.v_[var].get())
                    if var not in file_dict:
                        UI.lvprint(
                            1,
                            f"Setting {var} is missing from config, setting default value: {tab_value}",
                        )
                    file_value = self.set_value_type(var, file_dict.get(var, tab_value))

                    # Compare tab_value with value in file_dict
                    if file_value != tab_value:
                        _log_unsaved_config("tile", var, tab_value, file_value)
                        unsaved_changes["tile"] = True
                        break
        except FileNotFoundError:
            # Check Tile Config tab values against tile config values in the global config file
            try:
                with open(global_cfg_file) as f:
                    file_dict = dict(
                        line.strip().split("=") for line in f if line.strip()
                    )
                    for var in list_global_tile_vars:
                        # Config file doesn't have global_ prefix so we need to remove it
                        _var = var.replace(global_prefix, "")
                        tab_value = self.set_value_type(_var, self.v_[_var].get())
                        if _var not in file_dict:
                            UI.lvprint(
                                1,
                                f"Setting {_var} is missing from config, setting default value: {tab_value}",
                            )
                        file_value = self.set_value_type(
                            _var, file_dict.get(_var, tab_value)
                        )

                        if file_value != tab_value:
                            _log_unsaved_config("global", var, tab_value, file_value)
                            unsaved_changes["tile"] = True
                            break
            except FileNotFoundError:
                pass

        except (AttributeError, tk.TclError) as e:
            UI.log_exception(e)

        if not select_tile:
            # Check Global Config tab values against the global config file
            try:
                with open(global_cfg_file) as f:
                    file_dict = dict(
                        line.strip().split("=") for line in f if line.strip()
                    )
                    for var in list_global_tile_vars:
                        # Config file does not have global_ prefix so we need to remove it
                        _var = var.replace(global_prefix, "")
                        tab_value = self.set_value_type(_var, self.v_[var].get())
                        if _var not in file_dict:
                            UI.lvprint(
                                1,
                                f"Setting {_var} is missing from config, setting default value: {tab_value}",
                            )
                        file_value = self.set_value_type(
                            _var, file_dict.get(_var, tab_value)
                        )

                        if file_value != tab_value:
                            _log_unsaved_config("global", var, tab_value, file_value)
                            unsaved_changes["global"] = True
                            break
                    # Check App Config tab values against the global config file
                    for var in list_app_vars:
                        tab_value = self.set_value_type(var, self.v_[var].get())
                        if var not in file_dict:
                            UI.lvprint(
                                1,
                                f"Setting {var} is missing from config, setting default value: {tab_value}",
                            )
                        file_value = self.set_value_type(
                            var, file_dict.get(var, tab_value)
                        )

                        if file_value != tab_value:
                            _log_unsaved_config("global", var, tab_value, file_value)
                            unsaved_changes["application"] = True
                            break
            except FileNotFoundError:
                UI.log_event(
                    "Global configuration file (Ortho4XP.cfg) not found.",
                    level="ERROR",
                )
            except OSError as e:
                UI.log_exception(e)

        if any(unsaved_changes.values()):
            message = ""
            count = sum(unsaved_changes.values())
            if count == 1:
                key = next(key for key, value in unsaved_changes.items() if value)
                message = f"{key.capitalize()} Config tab has unsaved changes.\n"
            elif count == 2:
                keys = [
                    key.capitalize() for key, value in unsaved_changes.items() if value
                ]
                message = f"{', '.join(keys[:-1])} and {keys[-1]} Config tabs have unsaved changes.\n"
            elif count == 3:
                message = (
                    f"Tile, Global, and Application Config tabs have unsaved changes.\n"
                )
            # Appears to be an issue with macOS and using "Cancel" as sometimes it will present
            # the messagebox twice. Also happens rarely with "Yes/No".
            response = messagebox.askyesnocancel(
                "Unsaved Changes", f"{message}\nSave changes?", parent=self
            )
            if response is None:
                return "cancel"
            elif response:
                self.write_tile_cfg()
                self.write_global_cfg()
                self.write_app_cfg()

    def set_value_type(self, var: str, value) -> float | bool | str | list:
        """
        Return string based on type in cfg_vars except ints which
        will be returned as floats since this is used for comparing values.

        :param str value: value to be converted.
        :return: value in type based on cfg_vars
        """
        # Using floats for both int and float since we're going to compare them
        if cfg_vars[var]["type"] == int or cfg_vars[var]["type"] == float:
            return float(coerce_config_value(var, value, cfg_vars))
        return coerce_config_value(var, value, cfg_vars)

    def dict_to_cfg(self, file: str, cfg_dict: dict) -> None:
        """
        Convert dictionary to key=value format and write to file.

        :param str file: path to config file
        :param dict cfg_dict: dictionary to write to file
        :return: None
        """
        with open(file, "w") as config_file:
            for key, value in cfg_dict.items():
                config_file.write(f"{key}={value}\n")

    def cfg_to_dict(self, file: str) -> dict:
        """
        Read config file and return as a dictionary.

        :param str file: path to config file
        :return: dict
        """
        config_dict = {}
        with open(file) as config_file:
            for line in config_file:
                line = line.strip()
                if line and "=" in line:
                    key, value = line.split("=", 1)
                    config_dict[key.strip()] = value.strip()
        return config_dict

    def choose_dem(self, global_config=False):
        tmp = filedialog.askopenfilename(
            parent=self,
            title="Choose DEM file",
            filetypes=[
                ("DEM files", (".tif", ".hgt", ".raw", ".img")),
                ("all files", ".*"),
            ],
        )
        if tmp:
            custom_dem = "global_custom_dem" if global_config else "custom_dem"
            if not self.v_[custom_dem].get():
                self.v_[custom_dem].set(str(tmp))
            else:
                self.v_[custom_dem].set(self.v_[custom_dem].get() + ";" + str(tmp))

    def add_dem(self, global_config=False):
        tmp = filedialog.askopenfilename(
            parent=self,
            title="Choose DEM file",
            filetypes=[
                ("DEM files", (".tif", ".hgt", ".raw", ".img")),
                ("all files", ".*"),
            ],
        )
        if tmp:
            custom_dem = "global_custom_dem" if global_config else "custom_dem"
            if not self.v_[custom_dem].get():
                self.v_[custom_dem].set(str(tmp))
            else:
                self.v_[custom_dem].set(self.v_[custom_dem].get() + ";" + str(tmp))

    def choose_dir(self, item):
        tmp = filedialog.askdirectory(parent=self)
        if tmp:
            self.v_[item].set(str(tmp))

    def close_window(self) -> None:
        """Close the configuration window."""
        result = self.check_unsaved_changes()
        if result == "cancel":
            return
        self.destroy()

    def popup(self, header: str, input_text: str) -> None:
        """
        Popup window for hints.

        :param str header: top line of the body of the popup window
        :param str input_text: body of the popup window
        :return: None
        """
        self.popupwindow = tk.Toplevel()
        self.popupwindow.wm_title("Hint!")
        self.popupwindow.configure(background="light gray")

        ttk.Label(
            self.popupwindow,
            text=header,
            anchor=W,
            font=("TkBoldFont", 14),
            background="light gray",
        ).pack(side="top", fill="x", padx=5, pady=3)
        ttk.Label(
            self.popupwindow,
            text=input_text,
            wraplength=600,
            anchor=W,
            background="light gray",
        ).pack(side="top", fill="x", padx=5, pady=0)
        ttk.Button(self.popupwindow, text="Ok", command=self.popupwindow.destroy).pack(
            pady=5
        )
        return


def _log_debug_context(message: str, **context) -> None:
    UI.log_event(message, level="DEBUG", context=context)


def _log_zones_in_tile(tile_zones) -> None:
    _log_debug_context("Zones in tile found", tile_zones=tile_zones)


def _log_zones_saved_for_tile(lat, lon, tile_zones) -> None:
    _log_debug_context("Zones saved for tile", lat=lat, lon=lon, tile_zones=tile_zones)


def _log_unsaved_config(scope: str, var: str, current_value, config_file_value) -> None:
    _log_debug_context(
        f"Unsaved changes in {scope} config",
        var=var,
        current_value=current_value,
        config_file_value=config_file_value,
    )
