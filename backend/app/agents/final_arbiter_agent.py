from typing import Dict

from backend.app.models.reliability import ReliabilityAssessment


class FinalArbiterAgent:
    name = "final_arbiter_agent"

    def decide_language_policy(self, reliability: ReliabilityAssessment) -> Dict[str, str]:
        if reliability.strong_conclusion_allowed:
            return {
                "allowed_language": "limited_strong_conclusion",
                "message": "Strong conclusions may be stated with documented limitations.",
            }
        return {
            "allowed_language": "exploratory_only",
            "message": "Use exploratory language only. Do not state definitive biological or clinical conclusions.",
        }

