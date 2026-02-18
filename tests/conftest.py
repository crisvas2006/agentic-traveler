import sys
from unittest.mock import MagicMock

# Mock google.cloud.firestore before any tests run or imports happen
module_mock = MagicMock()
sys.modules["google.cloud.firestore"] = module_mock
