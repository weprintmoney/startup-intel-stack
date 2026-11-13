"""Service configuration — environment variables and their defaults."""

import os

# Backing store selection. ``disk`` is the default since v0.33.0; the former
# EXAMPLE_APP_STORE_URL (postgres/redis) is gone.
STORE = os.environ.get("EXAMPLE_APP_STORE", "disk")
DATA_DIR = os.environ.get("EXAMPLE_APP_DATA_DIR", "/var/lib/example_app")
S3_BUCKET = os.environ.get("EXAMPLE_APP_S3_BUCKET")
S3_PREFIX = os.environ.get("EXAMPLE_APP_S3_PREFIX", "")

# Authentication. Always required; ``--dev`` generates a local root token.
ROOT_TOKEN = os.environ.get("EXAMPLE_APP_ROOT_TOKEN")

# Licensing. Optional since v0.33.0 (free tier: 100,000 jobs per queue).
LICENSE_KEY = os.environ.get("EXAMPLE_APP_LICENSE_KEY")
FREE_TIER_MAX_JOBS = 100_000

# Enqueue defaults.
DEFAULT_VISIBILITY_TIMEOUT_S = 30
DEFAULT_MAX_ATTEMPTS = 5
