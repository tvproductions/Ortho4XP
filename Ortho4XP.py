#!/usr/bin/env python3
import os
import sys

Ortho4XP_dir = ".." if getattr(sys, "frozen", False) else "."
cmd_line = (
    "USAGE: Ortho4XP.py lat lon imagery zl (won't read a tile config)\n"
    "  OR:  Ortho4XP.py lat lon (with existing tile config file)\n"
    "  OR:  Ortho4XP.py validate-job build_job.toml [--json]\n"
    "  OR:  Ortho4XP.py build-job build_job.toml [--dry-run] [--json]"
)


def _source_root() -> str:
    if getattr(sys, "frozen", False):
        return Ortho4XP_dir
    return os.path.dirname(os.path.abspath(__file__))


def _ensure_src_path() -> None:
    src_path = os.path.join(_source_root(), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def _is_headless_command(argv: list[str]) -> bool:
    return len(argv) > 1 and argv[1] in {"validate-job", "build-job"}


def _dispatch_headless(argv: list[str]) -> int:
    cli_argv = list(argv[1:])
    if len(cli_argv) >= 2:
        cli_argv[1] = os.path.abspath(cli_argv[1])
    os.chdir(_source_root())
    _ensure_src_path()
    import O4_CLI_Run as CLI_RUN

    return CLI_RUN.main(cli_argv)

if __name__ == "__main__" and len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
    print(cmd_line)
    sys.exit(0)

if __name__ == "__main__" and _is_headless_command(sys.argv):
    sys.exit(_dispatch_headless(sys.argv))

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _proj_data_path = os.path.join(sys._MEIPASS, "pyproj", "proj_dir", "share", "proj")
    _lib_path = os.path.join(sys._MEIPASS, "_internal")
    os.environ["PROJ_DATA"] = _proj_data_path
    os.environ["DYLD_LIBRARY_PATH"] = (
        _lib_path + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
    )

from pyproj import datadir

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    datadir.set_data_dir(_proj_data_path)

_ensure_src_path()

import O4_File_Names as FNAMES

sys.path.append(FNAMES.Provider_dir)
import O4_Imagery_Utils as IMG
import O4_Build_Core as CORE
import O4_CLI_Utils as CLI
import O4_GUI_Utils as GUI
import O4_Config_Utils as CFG  # CFG imported last because it can modify other modules variables

runtime_dirs = (
    FNAMES.Preview_dir,
    FNAMES.Provider_dir,
    FNAMES.Extent_dir,
    FNAMES.Filter_dir,
    FNAMES.OSM_dir,
    FNAMES.Mask_dir,
    FNAMES.Imagery_dir,
    FNAMES.Elevation_dir,
    FNAMES.Geotiff_dir,
    FNAMES.Patch_dir,
    FNAMES.Tile_dir,
    FNAMES.Tmp_dir,
)


def ensure_runtime_dirs(utils_dir=FNAMES.Utils_dir, directories=runtime_dirs):
    if not os.path.isdir(utils_dir):
        print("Missing ", utils_dir, "directory, check your install. Exiting.")
        return False
    for directory in directories:
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
                print("Creating missing directory", directory)
            except OSError:
                print("Could not create required directory", directory, ". Exit.")
                return False
    return True


if __name__ == "__main__":
    if not ensure_runtime_dirs():
        sys.exit()
    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()
    if len(sys.argv) == 1:  # switch to the graphical interface
        Ortho4XP = GUI.Ortho4XP_GUI()
        Ortho4XP.mainloop()
        print("Bon vol!")
    else:  # sequel is only concerned with command line
        if len(sys.argv) < 3:
            print(cmd_line)
            sys.exit()
        try:
            lat = int(sys.argv[1])
            lon = int(sys.argv[2])
        except ValueError:
            print(cmd_line)
            sys.exit()
        if len(sys.argv) == 3:
            try:
                tile = CFG.Tile(lat, lon, "")
            except Exception as e:
                print(e)
                print("ERROR: could not read tile config file.")
                sys.exit()
        else:
            try:
                provider_code = sys.argv[3]
                zoomlevel = int(sys.argv[4])
                tile = CFG.Tile(lat, lon, "")
                setattr(tile, "default_website", provider_code)
                setattr(tile, "default_zl", zoomlevel)
            except (IndexError, ValueError):
                print(cmd_line)
                sys.exit()
        try:
            result = CORE.build_tile_all(tile)
            CLI.print_build_result(result)
        except Exception as e:
            print(e)
            print("Crash!")
