from typing import Dict, List


class ValidatorAgent:
    name = "validator_agent"

    def validate_mock_outputs(self, validation_methods: List[str]) -> Dict[str, object]:
        return {
            "mode": "mock",
            "methods": validation_methods,
            "concordant_methods": [],
            "discordant_methods": [],
            "note": "Validation concordance is not evaluated in Phase 1.",
        }

