import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from app.core.prompts import get_system_prompt, RISK_PARAMS_MAP, SYSTEM_PROMPT_TEMPLATE_V2026
from app.services.ia import IAService

class TestPromptsV2(unittest.TestCase):
    def setUp(self):
        self.ia = IAService()
        # Mock the API client to avoid real calls
        self.ia.client = MagicMock()

    def test_system_prompt_generation(self):
        """Test that get_system_prompt inserts correct constraints"""
        persona = "Sniper"
        risk = "Capital Preservation First"  # Min R:R = 1.5
        
        prompt = get_system_prompt(persona, risk, "15m")
        
        self.assertIn("Risk:Reward ratio MUST be >= 1.5", prompt)  # Updated to match RISK_PARAMS_MAP
        self.assertIn("Sniper", prompt)
        self.assertIn("STRICT JSON", prompt)

    def test_prompt_structure_english_only(self):
        """Ensure no French remnants in V2 templates"""
        self.assertNotIn("raisonnement", SYSTEM_PROMPT_TEMPLATE_V2026.lower())
        self.assertNotIn("analyse", SYSTEM_PROMPT_TEMPLATE_V2026.lower().replace("analysis", "")) # Check for French spelling

    def test_hard_constraint_enforcement_logic(self):
        """Test the _enforce_hard_constraints method in IAService"""
        risk_profile = "Capital Preservation First"  # Min R:R 1.5
        
        # Scenario 1: Good Trade (R:R = 3.0)
        signal_good = {"price": 100, "sl": 90, "tp": 130} # Risk 10, Reward 30
        ai_result_good = {"approved": True, "suggested_adjustments": {}}
        
        result = self.ia._enforce_hard_constraints(signal_good, ai_result_good, risk_profile)
        self.assertTrue(result["approved"])

        # Scenario 2: Bad Trade (R:R = 1.0)
        signal_bad = {"price": 100, "sl": 90, "tp": 110} # Risk 10, Reward 10
        ai_result_bad = {"approved": True, "suggested_adjustments": {}}
        
        result = self.ia._enforce_hard_constraints(signal_bad, ai_result_bad, risk_profile)
        self.assertFalse(result["approved"])
        self.assertEqual(result["rejection_reason_category"], "BAD_RR")
        self.assertIn("CRITICAL", result["reasoning"])

    def test_hard_constraint_with_ai_adjustments(self):
        """Test enforcement when AI suggests new SL/TP"""
        risk_profile = "Capital Preservation First"  # Min R:R 1.5
        
        # Signal is verified against AI's suggestions if present
        signal = {"price": 100, "sl": 90, "tp": 110} # Original R:R 1.0 (Bad)
        
        # AI Fixes it: New TP = 130 (R:R 3.0)
        ai_result_fixed = {
            "approved": True, 
            "suggested_adjustments": {"tp": 130}
        }
        
        result = self.ia._enforce_hard_constraints(signal, ai_result_fixed, risk_profile)
        self.assertTrue(result["approved"])

if __name__ == '__main__':
    unittest.main()
