import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock json_logic BEFORE importing app.services.rules_engine
mock_json_logic = MagicMock()
sys.modules['json_logic'] = mock_json_logic
mock_json_logic.jsonLogic = MagicMock(return_value=True)

from app.services.rules_engine import match_rule
from app.models import AutoAnalyzeRule

class TestRulesEngine(unittest.TestCase):
    def test_json_logic_called(self):
        """Test that if condition_json is present, jsonLogic is called."""
        rule = AutoAnalyzeRule(
            enabled=True,
            condition_json={"==": [{"var": "severity"}, "critical"]},
            alert_name_pattern="*",
            severity_pattern="*",
            instance_pattern="*",
            job_pattern="*"
        )
        
        # Reset mock
        mock_json_logic.jsonLogic.reset_mock()
        mock_json_logic.jsonLogic.return_value = True
        
        result = match_rule(rule, "alert", "critical", "inst", "job")
        
        self.assertTrue(result)
        mock_json_logic.jsonLogic.assert_called_once()
        call_args = mock_json_logic.jsonLogic.call_args
        self.assertEqual(call_args[0][0], rule.condition_json)
        self.assertEqual(call_args[0][1]['severity'], "critical")

    def test_legacy_fallback(self):
        """Test that if condition_json is None, legacy matching is used."""
        rule = AutoAnalyzeRule(
            enabled=True,
            condition_json=None,
            alert_name_pattern="test-*",
            severity_pattern="*",
            instance_pattern="*",
            job_pattern="*"
        )
        
        # Match
        self.assertTrue(match_rule(rule, "test-alert", "info", "inst", "job"))
        
        # No Match
        self.assertFalse(match_rule(rule, "other-alert", "info", "inst", "job"))

if __name__ == '__main__':
    unittest.main()
