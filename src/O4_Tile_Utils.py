import asyncio
import os
import queue
import shutil
import threading
import time

import O4_Build_Context as BC
import O4_Build_Models as MODELS
import O4_DSF_Utils as DSF
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Mask_Utils as MASK
import O4_Mesh_Utils as MESH
import O4_Overlay_Utils as OVL
import O4_Package_Metadata as PKG
import O4_Texture_Download_Scheduler as TDS
import O4_Tile_Texture_Conversion as TTC
import O4_UI_Utils as UI

# Step 3 activates a DSF only after its texture scheduler has stopped and the
# complete result batch has passed artifact finalization. Download, conversion,
# terrain-reference rewrite, and DSF replacement remain ordered boundaries;
# failure at any boundary leaves the previously active tile intact.
#
import O4_Vector_Map as VMAP

max_download_slots: int = 1
max_convert_slots: int = 4
max_texture_download_retries: int = 3
skip_downloads: bool = False
skip_converts: bool = False


################################################################################
async def async_download_textures(
    tile,
    download_queue,
    convert_queue,
    options=None,
):
    if options is None:
        options = TDS.DownloadTextureOptions(
            max_download_slots=max_download_slots,
            max_texture_download_retries=max_texture_download_retries,
        )
    return await TDS.async_download_textures(
        tile, download_queue, convert_queue, options
    )


def download_textures(
    tile,
    download_queue,
    convert_queue,
    workers=None,
    producer_done_event=None,
):
    options = TDS.DownloadTextureOptions(
        max_download_slots=max_download_slots,
        max_texture_download_retries=max_texture_download_retries,
        workers=workers,
        producer_done_event=producer_done_event,
    )
    return asyncio.run(
        async_download_textures(
            tile,
            download_queue,
            convert_queue,
            options,
        )
    )


################################################################################
def build_tile(tile, ctx=None):
    if ctx is None:
        ctx = BC.BuildContext()
    if ctx.is_working:
        return 0
    ctx.is_working = True
    ctx.red_flag = False
    UI.logprint("Step 3 for tile lat=", tile.lat, ", lon=", tile.lon, ": starting.")
    UI.vprint(
        0,
        "\nStep 3 : Building DSF/Imagery for tile "
        + FNAMES.short_latlon(tile.lat, tile.lon)
        + " : \n--------\n",
    )

    if not os.path.isfile(FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)):
        UI.lvprint(0, "ERROR: A mesh file must first be constructed for the tile!")
        UI.exit_message_and_bottom_line("")
        return 0

    timer = time.time()

    tile.write_to_config()

    if not IMG.initialize_local_combined_providers_dict(tile):
        UI.exit_message_and_bottom_line("")
        return 0

    try:
        if not os.path.exists(
            os.path.join(
                tile.build_dir,
                "Earth nav data",
                FNAMES.round_latlon(tile.lat, tile.lon),
            )
        ):
            os.makedirs(
                os.path.join(
                    tile.build_dir,
                    "Earth nav data",
                    FNAMES.round_latlon(tile.lat, tile.lon),
                )
            )
        if not os.path.isdir(os.path.join(tile.build_dir, "textures")):
            os.makedirs(os.path.join(tile.build_dir, "textures"))
        if ctx.cleaning_level > 1 and not tile.grouped:
            for f in os.listdir(os.path.join(tile.build_dir, "textures")):
                if f[-4:] != ".png":
                    continue
                try:
                    os.remove(os.path.join(tile.build_dir, "textures", f))
                except OSError as exc:
                    UI.vprint(3, exc)
        if not tile.grouped:
            try:
                shutil.rmtree(os.path.join(tile.build_dir, "terrain"))
            except OSError as exc:
                UI.vprint(3, exc)
        if not os.path.isdir(os.path.join(tile.build_dir, "terrain")):
            os.makedirs(os.path.join(tile.build_dir, "terrain"))
    except OSError as e:
        UI.lvprint(0, "ERROR: Cannot create tile subdirectories.")
        UI.vprint(3, e)
        UI.exit_message_and_bottom_line("")
        return 0

    download_queue = queue.Queue()
    convert_queue = queue.Queue()

    download_launched = False
    convert_launched = False
    convert_result_holder = {}
    download_workers = max_download_slots

    build_dsf_thread = threading.Thread(
        target=DSF.build_dsf, args=[tile, download_queue]
    )
    producer_done_event = threading.Event()

    download_thread = threading.Thread(
        target=download_textures,
        args=[
            tile,
            download_queue,
            convert_queue,
            download_workers,
            producer_done_event,
        ],
    )
    build_dsf_thread.start()
    if not skip_downloads:
        download_thread.start()
        download_launched = True
        if not skip_converts:
            UI.vprint(
                1,
                f"-> Opening convert queue and {max_convert_slots} conversion workers.",
            )
            convert_thread = threading.Thread(
                target=TTC.run_texture_conversion_scheduler,
                args=(convert_queue, convert_result_holder, max_convert_slots),
            )
            convert_thread.start()
            convert_launched = True
    build_dsf_thread.join()
    producer_done_event.set()
    if download_launched:
        download_thread.join()
        if convert_launched:
            convert_queue.put("quit")
            convert_thread.join()
            TTC.handle_texture_conversion_scheduler_result(tile, convert_result_holder)
    if _activation_is_blocked(ctx, tile, convert_launched, convert_result_holder):
        return 0
    UI.vprint(1, " *Activating DSF file.")
    dsf_file_name = os.path.join(
        tile.build_dir,
        "Earth nav data",
        FNAMES.long_latlon(tile.lat, tile.lon) + ".dsf",
    )
    try:
        os.replace(dsf_file_name + ".tmp", dsf_file_name)
    except OSError as exc:
        UI.vprint(0, "ERROR : could not rename DSF file, tile is not active.")
        UI.vprint(3, exc)
    if ctx.red_flag:
        UI.exit_message_and_bottom_line()
        return 0
    if ctx.cleaning_level > 1:
        try:
            os.remove(FNAMES.alt_file(tile))
        except OSError as exc:
            UI.vprint(3, exc)
        try:
            os.remove(FNAMES.input_node_file(tile))
        except OSError as exc:
            UI.vprint(3, exc)
        try:
            os.remove(FNAMES.input_poly_file(tile))
        except OSError as exc:
            UI.vprint(3, exc)
    if ctx.cleaning_level > 2:
        try:
            os.remove(FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon))
        except OSError as exc:
            UI.vprint(3, exc)
        try:
            os.remove(FNAMES.apt_file(tile))
        except OSError as exc:
            UI.vprint(3, exc)
    if ctx.cleaning_level > 1 and not tile.grouped:
        remove_unwanted_textures(tile)
    PKG.write_package_metadata(tile.build_dir, tile, "mesh")
    UI.timings_and_bottom_line(timer)
    UI.logprint("Step 3 for tile lat=", tile.lat, ", lon=", tile.lon, ": normal exit.")
    return 1


def _activation_is_blocked(ctx, tile, convert_launched, result_holder):
    """Report either interruption or finalization failure before DSF activation."""
    if ctx.red_flag:
        UI.exit_message_and_bottom_line()
        return True
    if convert_launched and not TTC.finalize_texture_conversion(tile, result_holder):
        UI.vprint(1, "Tile activation stopped after texture conversion failure.")
        return True
    return False


################################################################################
def build_all(tile):
    import O4_Build_Core as CORE

    result = CORE.build_tile_all(tile)
    return 1 if result.ok else 0


################################################################################
def build_tile_list(
    tile, list_lat_lon, do_osm, do_mesh, do_mask, do_dsf, do_ovl, override_cfg
):
    import O4_Build_Core as CORE

    steps = _batch_steps(do_osm, do_mesh, do_mask, do_dsf, do_ovl)
    plans = tuple(
        MODELS.BuildTilePlan(
            lat=lat,
            lon=lon,
            provider=getattr(tile, "default_website", ""),
            zoom_level=getattr(tile, "default_zl", 0),
            output_dir=tile.custom_build_dir or FNAMES.Tile_dir,
            custom_build_dir=tile.custom_build_dir,
            steps=steps,
            override_tile_config=override_cfg,
        )
        for lat, lon in sorted(list_lat_lon)
    )
    result = CORE.build_batch(MODELS.BuildPlan(plans))
    return 1 if result.ok else 0


def _batch_steps(do_osm, do_mesh, do_mask, do_dsf, do_ovl) -> tuple[str, ...]:
    steps: list[str] = []
    if do_osm:
        steps.append("vector")
    if do_mesh:
        steps.append("mesh")
    if do_mask:
        steps.append("masks")
    if do_dsf:
        steps.append("tile")
    if do_ovl:
        steps.append("overlays")
    return tuple(steps)


################################################################################
def remove_unwanted_textures(tile):
    texture_list = []
    for f in os.listdir(os.path.join(tile.build_dir, "terrain")):
        if f[-4:] != ".ter":
            continue
        if f[-5] == "y":  # water overlay
            texture_list.append("_".join(f[:-4].split("_")[:-2]) + ".dds")
        if f[-5] == "a":  # sea
            texture_list.append("_".join(f[:-4].split("_")[:-1]) + ".dds")
        else:
            texture_list.append(f.replace(".ter", ".dds"))
    for f in os.listdir(os.path.join(tile.build_dir, "textures")):
        if f[-4:] != ".dds":
            continue
        if f not in texture_list:
            print("Removing obsolete texture", f)
            try:
                os.remove(os.path.join(tile.build_dir, "textures", f))
            except OSError as exc:
                UI.vprint(3, exc)


def delete_incomplete_imgs(tile):
    """Delete orthophoto jpegs and dds that have white squares."""
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords not in IMG.incomplete_imgs:
        return
    file_name_list = IMG.incomplete_texture_file_names(tile_coords)
    for file_name in file_name_list:
        # Delete the orthophoto jpegs with white squares
        for root, _, files in os.walk(FNAMES.Imagery_dir):
            if file_name in files:
                file_path = os.path.join(root, file_name)
                os.remove(file_path)
                UI.lvprint(1, f"Deleted: {file_name} in {file_path}")

        # Delete the tile dds textures with white squares
        # file_name has .jpg extension, so create a variable for .dds extension as well
        base_name, _ = os.path.splitext(file_name)
        file_name_dds = f"{base_name}.dds"
        for root, _, files in os.walk(tile.build_dir):
            if file_name_dds in files:
                file_path = os.path.join(root, file_name_dds)
                os.remove(file_path)
                UI.lvprint(1, f"Deleted: {file_name_dds} in {file_path}")

    IMG.incomplete_imgs.pop(tile_coords, None)
