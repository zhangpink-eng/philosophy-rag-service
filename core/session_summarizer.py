from typing import Dict, List, Optional
from core.llm_client import LLMClient


class SessionSummarizer:
    """Auto-generate session summaries using LLM"""

    def __init__(self):
        self.llm = LLMClient()

    async def generate_summary(
        self,
        dialogue_history: List[Dict],
        scenario: str = "consultation"
    ) -> Dict:
        """
        Generate a session summary from dialogue history.

        Returns:
            Dict containing:
            - main_topic: str
            - key_questions: List[str]
            - user_insights: List[str]
            - contradictions_found: List[str]
            - avoidance_moments: List[str]
            - unresolved_questions: List[str]
            - homework: List[str]
            - next_session_focus: str
            - depth_score: float
            - engagement_score: float
        """
        if not dialogue_history:
            return self._empty_summary()

        # Build dialogue text
        dialogue_text = self._format_dialogue(dialogue_history)

        prompt = self._build_summary_prompt(dialogue_text, scenario)

        try:
            system_prompt = "You are a philosophical consultation analyst. Analyze the dialogue and provide structured insights."
            response = await self.llm.generate(system_prompt, prompt)

            # Parse LLM response into structured summary
            summary = self._parse_summary_response(response)
            return summary
        except Exception as e:
            print(f"Error generating summary: {e}")
            return self._empty_summary()

    def _format_dialogue(self, dialogue_history: List[Dict]) -> str:
        """Format dialogue history for prompt"""
        lines = []
        for turn in dialogue_history:
            role = "Client" if turn.get("role") == "user" else "Oscar"
            content = turn.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _build_summary_prompt(self, dialogue_text: str, scenario: str) -> str:
        """Build prompt for summary generation"""
        return f"""Please analyze the following philosophical consultation dialogue and provide a structured summary.

Scenario: {scenario}

Dialogue:
{dialogue_text}

Please provide a JSON summary with the following structure:
{{
    "main_topic": "The main topic discussed (1-2 sentences)",
    "key_questions": ["List of 2-4 key questions Oscar asked"],
    "user_insights": ["List of 2-4 insights the client reached"],
    "contradictions_found": ["List of contradictions or tensions discovered"],
    "avoidance_moments": ["List of moments where client avoided or deflected"],
    "unresolved_questions": ["List of questions that remain unresolved"],
    "homework": ["List of 1-2 thinking exercises for the client"],
    "next_session_focus": "Suggested focus for next session (1 sentence)",
    "depth_score": "Session depth rating 0-10",
    "engagement_score": "Client engagement rating 0-10"
}}

Provide ONLY the JSON, no additional text."""

    def _parse_summary_response(self, response: str) -> Dict:
        """Parse LLM response into summary dict"""
        try:
            # Try to extract JSON from response
            import json
            import re

            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                summary = json.loads(json_match.group())
                return self._validate_summary(summary)
        except Exception as e:
            print(f"Error parsing summary: {e}")

        return self._empty_summary()

    def _validate_summary(self, summary: Dict) -> Dict:
        """Ensure summary has all required fields"""
        default_summary = self._empty_summary()
        for key in default_summary:
            if key not in summary:
                summary[key] = default_summary[key]
        return summary

    def _empty_summary(self) -> Dict:
        """Return empty summary structure"""
        return {
            "main_topic": "",
            "key_questions": [],
            "user_insights": [],
            "contradictions_found": [],
            "avoidance_moments": [],
            "unresolved_questions": [],
            "homework": [],
            "next_session_focus": "",
            "depth_score": 0.0,
            "engagement_score": 0.0
        }
