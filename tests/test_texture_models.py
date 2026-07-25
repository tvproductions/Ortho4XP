import builtins
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


class TextureModelBoundaryTests(unittest.TestCase):
    def test_direct_import_does_not_load_mask_lifecycle_backend(self):
        module_name = "_isolated_texture_models"
        source = Path(__file__).resolve().parents[1] / "src" / "O4_Texture_Models.py"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            self.fail("unable to create isolated texture-model import spec")
        loader = spec.loader
        module = importlib.util.module_from_spec(spec)
        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == "O4_Texture_Mask_Lifecycle":
                raise AssertionError("model import reached mask lifecycle backend")
            return real_import(name, *args, **kwargs)

        with (
            mock.patch.dict(sys.modules, {module_name: module}),
            mock.patch.object(builtins, "__import__", side_effect=guarded_import),
        ):
            loader.exec_module(module)

        self.assertEqual(
            module.TextureCleanupPlan.__module__,
            module_name,
        )


if __name__ == "__main__":
    unittest.main()
