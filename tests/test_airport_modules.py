import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class AirportModuleImportTests(unittest.TestCase):
    def test_import_airport_discovery(self):
        import O4_Airport_Discovery as APT_DISC

        self.assertTrue(hasattr(APT_DISC, "discover_airport_names"))
        self.assertTrue(hasattr(APT_DISC, "attach_surfaces_to_airports"))
        self.assertTrue(hasattr(APT_DISC, "sort_and_reconstruct_runways"))
        self.assertTrue(hasattr(APT_DISC, "discard_unwanted_airports"))
        self.assertTrue(hasattr(APT_DISC, "list_airports_and_runways"))

    def test_import_airport_geometry(self):
        import O4_Airport_Geometry as APT_GEOM

        self.assertTrue(hasattr(APT_GEOM, "build_hangar_areas"))
        self.assertTrue(hasattr(APT_GEOM, "build_apron_areas"))
        self.assertTrue(hasattr(APT_GEOM, "build_taxiway_areas"))
        self.assertTrue(hasattr(APT_GEOM, "update_airport_boundaries"))
        self.assertTrue(hasattr(APT_GEOM, "build_airport_array"))
        self.assertTrue(hasattr(APT_GEOM, "smooth_raster_over_airports"))

    def test_import_airport_encoding(self):
        import O4_Airport_Encoding as APT_ENC

        self.assertTrue(hasattr(APT_ENC, "encode_runways_taxiways_and_aprons"))
        self.assertTrue(hasattr(APT_ENC, "encode_hangars"))
        self.assertTrue(hasattr(APT_ENC, "flatten_helipads"))
        self.assertTrue(hasattr(APT_ENC, "runway_chunks"))
        self.assertTrue(hasattr(APT_ENC, "chunk_min_size"))
        self.assertEqual(APT_ENC.runway_chunks, 100)
        self.assertEqual(APT_ENC.chunk_min_size, 10)


if __name__ == "__main__":
    unittest.main()
