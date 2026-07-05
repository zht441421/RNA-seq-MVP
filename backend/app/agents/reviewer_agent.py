from typing import Dict

from backend.app.models.reliability import ReliabilityAssessment


class ReviewerAgent:
    name = "reviewer_agent"

    def review(self, reliability: ReliabilityAssessment) -> Dict[str, object]:
        return {
            "grade": reliability.grade,
            "strong_conclusion_allowed": reliability.strong_conclusion_allowed,
            "review_note": "Strong claims are gated by reliability grade.",
        }

