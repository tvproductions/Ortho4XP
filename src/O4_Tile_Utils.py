import os
import time
import shutil
import queue
import threading
from collections import defaultdict
import O4_UI_Utils as UI
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Texture_Conversion_Scheduler as TCS
import O4_Vector_Map as VMAP
import O4_Mesh_Utils as MESH
import O4_Mask_Utils as MASK
import O4_DSF_Utils as DSF
import O4_Overlay_Utils as OVL
from O4_Parallel_Utils import parallel_launch, parallel_join

max_download_slots: int = 1
max_convert_slots: int = 4
max_texture_download_retries: int = 3
skip_downloads: bool = False
skip_converts: bool = False


################################################################################
def download_textures(
    tile,
    download_queue,
    convert_queue,
    workers=None,
    producer_done_event=None,
):
    worker_count = max(1, workers or max_download_slots)
    UI.vprint(1, f"-> Opening download queue with {worker_count} worker(s).")

    progress_lock = threading.Lock()
    progress_state = {"done": 0, "pending": 0}
    attempts = defaultdict(int)
    final_failures = []
    interrupted = False
    max_attempts = max(1, int(max_texture_download_retries))

    def _texture_failure_context(attrs):
        til_x_left, til_y_top, zoomlevel, provider_code = attrs
        file_name = FNAMES.jpeg_file_name_from_attributes(
            til_x_left, til_y_top, zoomlevel, provider_code
        )
        request_failures = IMG.failures_for_texture(file_name, provider_code)
        context = {
            "file_name": file_name,
            "provider_code": provider_code,
            "til_x_left": til_x_left,
            "til_y_top": til_y_top,
            "zoomlevel": zoomlevel,
            "status_code": "download_failed",
            "request_type": None,
        }
        if request_failures:
            last_failure = request_failures[-1]
            context.update(
                {
                    "status_code": last_failure.status_code,
                    "request_type": last_failure.request_type,
                    "url_type": last_failure.url_type,
                    "reason": last_failure.reason,
                }
            )
        return context

    def _update_progress_locked():
        denom = (
            progress_state["done"] + progress_state["pending"] + download_queue.qsize()
        )
        UI.progress_bar(2, int(100 * progress_state["done"] / denom) if denom else 100)

    def _download_task(*attrs):
        nonlocal interrupted

        if UI.red_flag:
            interrupted = True
            return 0

        attrs = tuple(attrs)
        with progress_lock:
            progress_state["pending"] += 1
            _update_progress_locked()

        try:
            ok = IMG.build_jpeg_ortho(tile, *attrs)
        except Exception as err:
            UI.vprint(2, f"Download failed: {err}")
            ok = 0

        should_retry = False
        with progress_lock:
            progress_state["pending"] -= 1
            if ok:
                progress_state["done"] += 1
                attempts.pop(attrs, None)
            else:
                attempt = attempts[attrs] + 1
                attempts[attrs] = attempt
                should_retry = attempt < max_attempts and not UI.red_flag
                if not should_retry:
                    final_failures.append(_texture_failure_context(attrs))
                    attempts.pop(attrs, None)
            _update_progress_locked()

        if ok:
            convert_queue.put((tile, *attrs))
        elif should_retry:
            download_queue.put(attrs)
            with progress_lock:
                _update_progress_locked()

        if UI.red_flag:
            interrupted = True

        return 1 if ok else 0

    if producer_done_event is None:
        producer_done_event = threading.Event()
        producer_done_event.set()

    workers_list = parallel_launch(_download_task, download_queue, worker_count)

    while not producer_done_event.is_set() and not UI.red_flag:
        time.sleep(0.05)

    while not UI.red_flag:
        with progress_lock:
            pending = progress_state["pending"]
        if download_queue.empty() and pending == 0:
            break
        time.sleep(0.05)

    for _ in range(worker_count):
        download_queue.put("quit")

    parallel_join(workers_list)

    UI.progress_bar(2, 100)
    if interrupted or UI.red_flag:
        UI.vprint(1, "Download process interrupted.")
        return 0
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    summary = IMG.imagery_download_summary(tile_coords, final_failures)
    if summary:
        provider_counts = ", ".join(
            f"{provider}={count}"
            for provider, count in sorted(summary["by_provider"].items())
        )
        status_counts = ", ".join(
            f"{status}={count}"
            for status, count in sorted(summary["by_status"].items())
        )
        request_counts = ", ".join(
            f"{request_type}={count}"
            for request_type, count in sorted(summary["by_request_type"].items())
        )
        UI.vprint(
            1,
            "Imagery download summary:",
            f"{summary['total_textures']} incomplete or failed texture(s)",
            f"for tile {tile_coords}.",
            f"Providers: {provider_counts}.",
            f"Statuses: {status_counts}.",
            f"Request types: {request_counts}.",
        )
    if progress_state["done"]:
        UI.vprint(1, " *Download of textures completed.")
    return 1


################################################################################
def _report_texture_conversion_result(tile, result):
    if result.interrupted:
        UI.vprint(1, "DDS conversion process interrupted.")
        return
    if result.failed:
        provider_counts = _texture_conversion_provider_counts(result.failures)
        UI.vprint(
            1,
            "DDS conversion summary:",
            f"{result.failed} failed texture(s)",
            f"for tile {FNAMES.short_latlon(tile.lat, tile.lon)}.",
            f"Providers: {provider_counts}.",
        )
        return
    if result.completed >= 1:
        UI.vprint(1, " *DDS conversion of textures completed.")


def _texture_conversion_provider_counts(failures):
    counts = defaultdict(int)
    for failure in failures:
        counts[failure.provider_code or "unknown"] += 1
    return ", ".join(
        f"{provider}={count}" for provider, count in sorted(counts.items())
    )


def _run_texture_conversion_scheduler(convert_queue, result_holder):
    try:
        result_holder["result"] = TCS.run_texture_conversion_queue(
            convert_queue,
            max_convert_slots,
            convert_texture=IMG.convert_texture,
        )
    except Exception as exc:
        result_holder["exception"] = exc


def _handle_texture_conversion_scheduler_result(tile, result_holder):
    if "exception" in result_holder:
        exc = result_holder["exception"]
        UI.vprint(1, "DDS conversion scheduler failed:", str(exc))
        UI.vprint(3, exc)
        UI.red_flag = True
        return
    result = result_holder.get("result")
    if result is None:
        UI.vprint(1, "DDS conversion scheduler failed:", "missing conversion result.")
        UI.red_flag = True
        return
    _report_texture_conversion_result(tile, result)


################################################################################
def build_tile(tile):
    if UI.is_working:
        return 0
    UI.is_working = 1  # ty:ignore[invalid-assignment]
    UI.red_flag = False
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
        if UI.cleaning_level > 1 and not tile.grouped:
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
                "-> Opening convert queue and",
                max_convert_slots,
                "conversion workers.",
            )
            convert_thread = threading.Thread(
                target=_run_texture_conversion_scheduler,
                args=(convert_queue, convert_result_holder),
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
            _handle_texture_conversion_scheduler_result(
                tile,
                convert_result_holder,
            )
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
    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0
    if UI.cleaning_level > 1:
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
    if UI.cleaning_level > 2:
        try:
            os.remove(FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon))
        except OSError as exc:
            UI.vprint(3, exc)
        try:
            os.remove(FNAMES.apt_file(tile))
        except OSError as exc:
            UI.vprint(3, exc)
    if UI.cleaning_level > 1 and not tile.grouped:
        remove_unwanted_textures(tile)
    UI.timings_and_bottom_line(timer)
    UI.logprint("Step 3 for tile lat=", tile.lat, ", lon=", tile.lon, ": normal exit.")
    return 1


################################################################################
def build_all(tile):
    VMAP.build_poly_file(tile)
    if UI.red_flag:
        UI.exit_message_and_bottom_line("")
        return 0
    MESH.build_mesh(tile)
    if UI.red_flag:
        UI.exit_message_and_bottom_line("")
        return 0
    MASK.build_masks(tile)
    if UI.red_flag:
        UI.exit_message_and_bottom_line("")
        return 0
    build_tile(tile)
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords in IMG.incomplete_imgs:
        UI.lvprint(
            1,
            f"Attempting to rebuild textures with white squares: "
            f"{IMG.incomplete_texture_file_names(tile_coords)}",
        )
        delete_incomplete_imgs(tile)
        build_tile(tile)
    if UI.red_flag:
        UI.exit_message_and_bottom_line("")
        return 0
    UI.is_working = 0  # ty:ignore[invalid-assignment]
    if IMG.incomplete_imgs:
        UI.lvprint(
            0,
            f"\nERROR: Parts of the following images could not be obtained "
            f"and have been filled with white: "
            f"{IMG.incomplete_texture_file_names_by_tile()}",
        )
    return 1


################################################################################
def build_tile_list(
    tile, list_lat_lon, do_osm, do_mesh, do_mask, do_dsf, do_ovl, override_cfg
):
    if UI.is_working:
        return 0
    UI.red_flag = 0  # ty:ignore[invalid-assignment]
    timer = time.time()
    UI.lvprint(0, "Batch build launched for a number of", len(list_lat_lon), "tiles.")
    k = 0
    for lat, lon in list_lat_lon:
        k += 1
        UI.vprint(
            1,
            "Dealing with tile ",
            k,
            "/",
            len(list_lat_lon),
            ":",
            FNAMES.short_latlon(lat, lon),
        )
        (tile.lat, tile.lon) = (lat, lon)
        tile.build_dir = FNAMES.build_dir(tile.lat, tile.lon, tile.custom_build_dir)
        tile.dem = None
        if override_cfg:
            tile.read_from_config(use_global=True)
        else:
            tile.read_from_config()
        if do_osm or do_mesh or do_dsf:
            tile.make_dirs()
        if do_osm:
            VMAP.build_poly_file(tile)
            if UI.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        if do_mesh:
            MESH.build_mesh(tile)
            if UI.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        if do_mask:
            MASK.build_masks(tile)
            if UI.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        if do_dsf:
            tile_coords = FNAMES.short_latlon(lat, lon)
            build_tile(tile)
            if tile_coords in IMG.incomplete_imgs:
                UI.lvprint(
                    1,
                    f"Attempting to rebuild textures with white squares: "
                    f"{IMG.incomplete_texture_file_names(tile_coords)}",
                )
                delete_incomplete_imgs(tile)
                build_tile(tile)
            if UI.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        if do_ovl:
            OVL.build_overlay(lat, lon)
            if UI.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        try:
            UI.gui.earth_window.canvas.delete(  # ty:ignore[unresolved-attribute]
                UI.gui.earth_window.dico_tiles_todo[(lat, lon)]  # ty:ignore[unresolved-attribute]
            )
            UI.gui.earth_window.dico_tiles_todo.pop((lat, lon), None)  # ty:ignore[unresolved-attribute]
        except (AttributeError, KeyError) as exc:
            UI.vprint(3, exc)
    UI.lvprint(0, "Batch process completed in", UI.nicer_timer(time.time() - timer))
    if IMG.incomplete_imgs:
        UI.lvprint(
            0,
            f"\nERROR: Parts of the following images could not be obtained "
            f"and have been filled with white: "
            f"{IMG.incomplete_texture_file_names_by_tile()}",
        )
    return 1


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
