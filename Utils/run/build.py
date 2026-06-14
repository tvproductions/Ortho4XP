#!/usr/bin/env python3

import os
import subprocess
import sys

sys.dont_write_bytecode = True

import configure

if __name__ == "__main__":
    (build_type, os_cfg) = configure.parse_args(sys.argv)
    for cfg in os_cfg:
        print()
        print("--------------------------------------------------------")
        print(
            "Building Ortho4XP C executables in {:s} mode for {:s}.".format(
                build_type, cfg["name"]
            )
        )
        print("--------------------------------------------------------")
        cmd = [
            "cmake",
            "--build",
            os.path.join("build", build_type.lower(), cfg["dir"]),
        ]
        print("Executing : " + " ".join(cmd))
        subprocess.run(cmd, check=True)
        print("Build done for " + cfg["name"] + ".")
