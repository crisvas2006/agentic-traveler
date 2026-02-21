import sys
import os
from unittest.mock import MagicMock

# Mock google.cloud.firestore for unit tests so they don't need
# real GCP credentials.  Integration tests need the real module.
#
# When the user runs `pytest -m integration`, the _INTEGRATION_TESTS
# env var must be set so we skip this mock:
#   _INTEGRATION_TESTS=1 pytest -m integration -v
#
# Alternatively, we detect if the real module is importable and skip
# the mock only when integration tests are explicitly requested via env.
if not os.getenv("_INTEGRATION_TESTS"):
    module_mock = MagicMock()
    sys.modules["google.cloud.firestore"] = module_mock
