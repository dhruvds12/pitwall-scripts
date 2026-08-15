"""
Configuration and environment loading utilities.
"""

import os
import sys


def load_env_file(filepath=".env"):
    """Load key-value pairs from a local .env file into os.environ."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    val = val.strip().strip("'\"")
                    key = key.strip()
                    if key:
                        os.environ[key] = val
        except Exception as e:
            print(f"Warning: Failed to read {filepath}: {e}", file=sys.stderr)
