import importlib


setuptools = importlib.import_module("setuptools")

setuptools.setup(
    name="pymesh",
    version="1.0",
    ext_modules=[
        setuptools.Extension(
            "pymesh", ["pymesh.c"], include_dirs=["/home/oscarpilote/Ortho4XP/src/C/"]
        )
    ],
)
