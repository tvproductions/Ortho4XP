import json
import os
import tempfile
import unittest
from types import SimpleNamespace

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Cfg_Vars as CFGV


def _tile(tmpdir, **overrides):
    values = {
        key: definition["default"] for key, definition in CFGV.cfg_tile_vars.items()
    }
    values.update(overrides)
    return SimpleNamespace(lat=12, lon=-123, build_dir=tmpdir, **values)


class BuildCacheTests(unittest.TestCase):
    def test_parameter_hash_is_deterministic_for_equal_parameters(self):
        import O4_Build_Cache as CACHE

        with tempfile.TemporaryDirectory() as tmpdir:
            first = _tile(
                tmpdir,
                zone_list=[[[12, -123], 18, "BI"]],
                masks_custom_extent={"b": 2, "a": 1},
            )
            second = _tile(
                tmpdir,
                zone_list=[[[12, -123], 18, "BI"]],
                masks_custom_extent={"a": 1, "b": 2},
            )

            self.assertEqual(CACHE.parameter_hash(first), CACHE.parameter_hash(second))

    def test_parameter_hash_changes_when_tile_parameter_changes(self):
        import O4_Build_Cache as CACHE

        with tempfile.TemporaryDirectory() as tmpdir:
            first = _tile(tmpdir, default_zl=16)
            second = _tile(tmpdir, default_zl=17)

            self.assertNotEqual(
                CACHE.parameter_hash(first), CACHE.parameter_hash(second)
            )

    def test_write_cache_metadata_creates_tile_meta_json(self):
        import O4_Build_Cache as CACHE

        with tempfile.TemporaryDirectory() as tmpdir:
            tile = _tile(tmpdir, default_website="BI", default_zl=17)

            CACHE.write_cache_metadata(tile)

            with open(CACHE.tile_meta_path(tile), encoding="utf-8") as f:
                metadata = json.load(f)

        self.assertEqual(metadata["schema_version"], CACHE.SCHEMA_VERSION)
        self.assertEqual(metadata["tile"], {"lat": 12, "lon": -123})
        self.assertEqual(metadata["build_parameters"]["default_website"], "BI")
        self.assertEqual(metadata["build_parameters"]["default_zl"], 17)
        self.assertEqual(metadata["parameter_hash"], CACHE.parameter_hash(tile))

    def test_matching_metadata_returns_cache_hit(self):
        import O4_Build_Cache as CACHE

        with tempfile.TemporaryDirectory() as tmpdir:
            tile = _tile(tmpdir, default_zl=17)
            CACHE.write_cache_metadata(tile)

            hit = CACHE.read_cache_hit(tile)

            self.assertIsNotNone(hit)
            if hit is None:
                raise AssertionError("expected cache hit")
            self.assertEqual(hit.metadata_path, CACHE.tile_meta_path(tile))
            self.assertEqual(hit.parameter_hash, CACHE.parameter_hash(tile))

    def test_stale_metadata_returns_cache_miss(self):
        import O4_Build_Cache as CACHE

        with tempfile.TemporaryDirectory() as tmpdir:
            old_tile = _tile(tmpdir, default_zl=16)
            new_tile = _tile(tmpdir, default_zl=17)
            CACHE.write_cache_metadata(old_tile)

            self.assertIsNone(CACHE.read_cache_hit(new_tile))

    def test_malformed_metadata_returns_cache_miss(self):
        import O4_Build_Cache as CACHE

        with tempfile.TemporaryDirectory() as tmpdir:
            tile = _tile(tmpdir)
            with open(CACHE.tile_meta_path(tile), "w", encoding="utf-8") as f:
                f.write("{not json")

            self.assertIsNone(CACHE.read_cache_hit(tile))

    def test_missing_metadata_returns_cache_miss(self):
        import O4_Build_Cache as CACHE

        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertIsNone(CACHE.read_cache_hit(_tile(tmpdir)))

    def test_tile_meta_path_uses_tile_build_dir(self):
        import O4_Build_Cache as CACHE

        with tempfile.TemporaryDirectory() as tmpdir:
            tile = _tile(tmpdir)

            self.assertEqual(
                CACHE.tile_meta_path(tile),
                os.path.join(tmpdir, "tile_meta.json"),
            )


if __name__ == "__main__":
    unittest.main()
