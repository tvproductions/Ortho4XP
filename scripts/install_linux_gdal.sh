#!/usr/bin/env bash
# Build the native library that matches the project-locked Python bindings.
# Install the development prerequisites documented in CONTRIBUTING.md first.
set -euo pipefail

GDAL_VERSION=3.13.3
GDAL_SHA256=5e0c388d83da2d686cc00a40272882432cdb54edff43d4af173e532844a0a0ea
GDAL_PREFIX="${1:?Usage: bash scripts/install_linux_gdal.sh ABSOLUTE_INSTALL_PREFIX}"
case "$GDAL_PREFIX" in
    /*) ;;
    *) echo "The GDAL installation prefix must be absolute." >&2; exit 2 ;;
esac

build_root="$(mktemp -d "${TMPDIR:-/tmp}/ortho4xp-gdal.XXXXXXXX")"
trap 'rm -rf -- "$build_root"' EXIT
archive="$build_root/gdal-$GDAL_VERSION.tar.gz"
curl --fail --location --retry 3 \
    "https://github.com/OSGeo/gdal/releases/download/v$GDAL_VERSION/gdal-$GDAL_VERSION.tar.gz" \
    --output "$archive"
printf '%s  %s\n' "$GDAL_SHA256" "$archive" | sha256sum --check
tar -xzf "$archive" -C "$build_root"
cmake -S "$build_root/gdal-$GDAL_VERSION" -B "$build_root/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$GDAL_PREFIX" \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DBUILD_TESTING=OFF -DBUILD_PYTHON_BINDINGS=OFF
cmake --build "$build_root/build" --parallel "${GDAL_BUILD_JOBS:-2}"
cmake --install "$build_root/build"
installed_version="$("$GDAL_PREFIX/bin/gdal-config" --version)"
if [ "$installed_version" != "$GDAL_VERSION" ]; then
    echo "GDAL native/binding mismatch: $installed_version != $GDAL_VERSION" >&2
    exit 1
fi
printf 'Installed native GDAL %s at %s\n' "$installed_version" "$GDAL_PREFIX"
