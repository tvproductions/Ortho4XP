import os
import shutil
import sys
import time
from types import SimpleNamespace

import O4_File_Names as FNAMES
import O4_Package_Metadata as PKG
import O4_Subprocess_Utils as SP
import O4_UI_Utils as UI

# the following is meant to be modified directly by users who need it (in the
# config window, not here!)
ovl_exclude_pol = [0]
ovl_exclude_net = []

# the following is meant to be modified by the CFG module at run time
custom_overlay_src = ""
custom_overlay_src_alternate = ""

if "dar" in sys.platform or "win" in sys.platform:
    unzip_cmd = SP.resolve_tool("7z")
    dsftool_cmd = SP.resolve_tool("DSFTool")
else:
    unzip_cmd = SP.resolve_tool("7z")
    dsftool_cmd = SP.resolve_tool("DSFTool")

# Overlay extraction still exposes these command variables for import-time
# compatibility with other modules.
# Execution, output capture, and logging are centralized in O4_Subprocess_Utils.
# The overlay workflow keeps its existing retry and exit behavior.


################################################################################
def build_overlay(lat, lon):
    if UI.is_working:
        return 0
    UI.is_working = 1  # ty:ignore[invalid-assignment]
    timer = time.time()
    UI.logprint("Step 4 for tile lat=", lat, ", lon=", lon, ": starting.")
    UI.vprint(
        0,
        "\nStep 4 : Extracting overlay for tile "
        + FNAMES.short_latlon(lat, lon)
        + " : \n--------\n",
    )
    file_to_sniff = os.path.join(
        custom_overlay_src,
        "Earth nav data",
        FNAMES.long_latlon(lat, lon) + ".dsf",
    )
    if not os.path.exists(file_to_sniff):
        file_to_sniff = os.path.join(
            custom_overlay_src_alternate,
            "Earth nav data",
            FNAMES.long_latlon(lat, lon) + ".dsf",
        )
    if not os.path.exists(file_to_sniff):
        UI.exit_message_and_bottom_line(
            "   ERROR: file ",
            file_to_sniff,
            "absent. Recall that the overlay source directory needs to be set ",
            "in the config window first.",
        )
        return 0
    file_to_sniff_loc = os.path.join(
        FNAMES.Tmp_dir, FNAMES.short_latlon(lat, lon) + ".dsf"
    )
    UI.vprint(1, "-> Making a copy of the original overlay DSF in tmp dir")
    try:
        shutil.copy(file_to_sniff, file_to_sniff_loc)
    except OSError as exc:
        UI.exit_message_and_bottom_line(
            "   ERROR: could not copy it. Disk full, write permissions, erased",
            " tmp dir ?",
        )
        UI.vprint(3, exc)
        return 0
    dsfid = _read_dsf_signature(file_to_sniff_loc)
    if dsfid == "7z":
        UI.vprint(1, "-> The original DSF is a 7z archive, uncompressing...")
        os.replace(file_to_sniff_loc, file_to_sniff_loc + ".7z")
        SP.run_external_tool(
            "7z",
            ["e", f"-o{FNAMES.Tmp_dir}", f"{file_to_sniff_loc}.7z"],
            executable=unzip_cmd,
        )
        os.remove(file_to_sniff_loc + ".7z")
    UI.vprint(1, "-> Converting the copy to text format")
    dsfconvertcmd = [
        dsftool_cmd,
        "-dsf2text",
        file_to_sniff_loc,
        os.path.join(FNAMES.Tmp_dir, FNAMES.short_latlon(lat, lon) + "_tmp_dsf.txt"),
    ]
    result = SP.run_external_tool(
        "DSFTool",
        dsfconvertcmd[1:],
        executable=dsfconvertcmd[0],
        stream_stdout=True,
        stdout_handler=lambda line: UI.vprint(1, "     " + line),
    )
    if not result.ok:
        UI.exit_message_and_bottom_line("   ERROR: DSFTool crashed.")
        return 0
    UI.vprint(1, "-> Selecting overlays for copy/paste")
    _write_overlay_without_mesh(lat, lon)
    UI.vprint(1, "-> Converting back the text DSF to binary format")
    dsfconvertcmd = [
        dsftool_cmd,
        "-text2dsf",
        os.path.join(
            FNAMES.Tmp_dir,
            FNAMES.short_latlon(lat, lon) + "_tmp_dsf_without_mesh.txt",
        ),
        os.path.join(
            FNAMES.Tmp_dir,
            FNAMES.short_latlon(lat, lon) + "_tmp_dsf_without_mesh.dsf",
        ),
    ]
    SP.run_external_tool(
        "DSFTool",
        dsfconvertcmd[1:],
        executable=dsfconvertcmd[0],
        stream_stdout=True,
        stdout_handler=lambda line: print("     " + line),
    )
    dest_dir = os.path.join(
        FNAMES.Overlay_dir, "Earth nav data", FNAMES.round_latlon(lat, lon)
    )
    UI.vprint(1, "-> Copying the final overlay DSF in " + dest_dir)
    if not os.path.exists(dest_dir):
        try:
            os.makedirs(dest_dir)
        except OSError as exc:
            UI.exit_message_and_bottom_line(
                "   ERROR: could not create destination directory " + str(dest_dir)
            )
            UI.vprint(3, exc)
            return 0
    shutil.copy(
        os.path.join(
            FNAMES.Tmp_dir,
            FNAMES.short_latlon(lat, lon) + "_tmp_dsf_without_mesh.dsf",
        ),
        os.path.join(dest_dir, FNAMES.short_latlon(lat, lon) + ".dsf"),
    )
    os.remove(
        os.path.join(
            FNAMES.Tmp_dir,
            FNAMES.short_latlon(lat, lon) + "_tmp_dsf_without_mesh.dsf",
        )
    )
    os.remove(
        os.path.join(
            FNAMES.Tmp_dir,
            FNAMES.short_latlon(lat, lon) + "_tmp_dsf_without_mesh.txt",
        )
    )
    os.remove(
        os.path.join(FNAMES.Tmp_dir, FNAMES.short_latlon(lat, lon) + "_tmp_dsf.txt")
    )
    os.remove(file_to_sniff_loc)
    try:
        os.remove(
            os.path.join(
                FNAMES.Tmp_dir,
                FNAMES.short_latlon(lat, lon) + "_tmp_dsf.txt.elevation.raw",
            )
        )
        os.remove(
            os.path.join(
                FNAMES.Tmp_dir,
                FNAMES.short_latlon(lat, lon) + "_tmp_dsf.txt.sea_level.raw",
            )
        )
    except OSError as exc:
        UI.vprint(3, exc)
    overlay_package_dir = os.path.dirname(os.path.dirname(dest_dir))
    PKG.write_package_metadata(
        overlay_package_dir, SimpleNamespace(lat=lat, lon=lon), "overlay"
    )
    UI.timings_and_bottom_line(timer)
    return 1


def _read_dsf_signature(path):
    with open(path, "rb") as f:
        return f.read(2).decode("ascii")


def _write_overlay_without_mesh(lat, lon):
    source_path = os.path.join(
        FNAMES.Tmp_dir, FNAMES.short_latlon(lat, lon) + "_tmp_dsf.txt"
    )
    target_path = os.path.join(
        FNAMES.Tmp_dir, FNAMES.short_latlon(lat, lon) + "_tmp_dsf_without_mesh.txt"
    )
    with open(source_path) as source, open(target_path, "w") as target:
        _copy_overlay_records(source, target)


def _copy_overlay_records(source, target):
    line = source.readline()
    target.write("PROPERTY sim/overlay 1\n")
    pol_type = 0
    pol_dict = {}
    exclude_set_updated = False
    full_ovl_exclude_pol = set(ovl_exclude_pol)
    while line:
        if "PROPERTY" in line:
            target.write(line)
        elif "POLYGON_DEF" in line:
            level = 2 if "facade" not in line else 3
            pol_dict[pol_type] = line.split()[1]
            UI.vprint(level, pol_type, ":", pol_dict[pol_type])
            pol_type += 1
            target.write(line)
        elif "NETWORK_DEF" in line:
            target.write(line)
        elif "BEGIN_POLYGON" in line:
            full_ovl_exclude_pol, exclude_set_updated, line = _copy_polygon_record(
                source,
                target,
                line,
                pol_dict,
                full_ovl_exclude_pol,
                exclude_set_updated,
            )
        elif "BEGIN_SEGMENT" in line:
            line = _copy_segment_record(source, target, line)
        line = source.readline()


def _copy_polygon_record(
    source, target, line, pol_dict, full_ovl_exclude_pol, exclude_set_updated
):
    if not exclude_set_updated:
        full_ovl_exclude_pol = _resolved_polygon_exclusions(
            full_ovl_exclude_pol, pol_dict
        )
        exclude_set_updated = True
    pol_type = int(line.split()[1])
    if pol_type not in full_ovl_exclude_pol:
        while line and ("END_POLYGON" not in line):
            target.write(line)
            line = source.readline()
        target.write(line)
    else:
        while line and ("END_POLYGON" not in line):
            line = source.readline()
    return full_ovl_exclude_pol, exclude_set_updated, line


def _resolved_polygon_exclusions(full_ovl_exclude_pol, pol_dict):
    resolved = set()
    for item in full_ovl_exclude_pol:
        if isinstance(item, int):
            resolved.add(item)
        elif isinstance(item, str):
            if item and item[0] == "!":
                item = item[1:]
                resolved = resolved.union(
                    [k for k in pol_dict if item not in pol_dict[k]]
                )
            else:
                resolved = resolved.union([k for k in pol_dict if item in pol_dict[k]])
    return resolved


def _copy_segment_record(source, target, line):
    road_type = int(line.split()[2])
    excluded = (
        road_type in ovl_exclude_net or "" in ovl_exclude_net or "*" in ovl_exclude_net
    )
    while line and ("END_SEGMENT" not in line):
        if not excluded:
            target.write(line)
        line = source.readline()
    if not excluded:
        target.write(line)
    return line
