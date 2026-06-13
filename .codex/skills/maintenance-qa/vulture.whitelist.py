# Vulture whitelist for Ortho4XP
#
# This file lists known dead code that is intentional or acceptable.
# Each entry includes a justification comment.

# Unused/ directory contains legacy code that may be revived
Unused/

# Test fixtures and helpers that are imported dynamically
tests/_path.py
tests/_imagery_color_normalization_helpers.py
tests/_imagery_geotiff_conversion_helpers.py
tests/_dsf_header_bridge_helpers.py

# Provider definitions are loaded dynamically
Providers/*.lay.json

# Extent definitions are loaded dynamically
Extents/*.ext.json

# Color filter definitions are loaded dynamically
Filters/*.flt.json

# Combined provider definitions are loaded dynamically
Providers/*.comb.json
