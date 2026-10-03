"""
Pytest configuration for PostVisit AI tests.
Ensures project root is added to sys.path and sandbox test environment is initialized.
"""

import os
import sys
from pathlib import Path

# Enforce test/sandbox environment for all automated test runs
os.environ["APP_ENV"] = "test"
os.environ.setdefault("SUPABASE_JWT_SECRET", "postvisit-sandbox-secret-key-32-chars-long-test-only")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

