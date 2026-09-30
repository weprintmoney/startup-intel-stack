"""Service configuration — environment variables and their defaults."""

import os

# Backing store selection. ``disk`` is the default since v0.17.0; the former
# EXAMPLE_APP_CONNECTION_STRING (postgres/redis) is gone.
DB_TYPE = os.environ.get("EXAMPLE_APP_DB_TYPE", "disk")
DISK_PATH = os.environ.get("EXAMPLE_APP_DISK_PATH", "/var/lib/example_app")
S3_BUCKET = os.environ.get("EXAMPLE_APP_S3_BUCKET")
S3_PREFIX = os.environ.get("EXAMPLE_APP_S3_PREFIX", "")

# Authentication. Unset -> auth disabled; set -> root key or per-user exk_ token.
SERVICE_ROOT_KEY = os.environ.get("EXAMPLE_APP_SERVICE_ROOT_KEY")

# Licensing. Optional since v0.17.0 (free tier: 1,000,000 items per index).
API_KEY = os.environ.get("EXAMPLE_APP_API_KEY")
FREE_TIER_MAX_ITEMS = 1_000_000

# Query defaults.
DEFAULT_TOP_K = 100
DEFAULT_RERANK_MULT = 4
