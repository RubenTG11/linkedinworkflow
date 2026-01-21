"""Critic agent for reviewing and improving LinkedIn posts."""
import json
from typing import Dict, Any, Optional, List
from loguru import logger

from src.agents.base import BaseAgent


class CriticAgent(BaseAgent):
    """Agent for critically reviewing LinkedIn posts and suggesting improvements."""

    def __init__(self):
        """Initialize critic agent."""
        super().__init__("Critic")

    async def process(
        self,
        post: str,
        profile_analysis: Dict[str, Any],
        topic: Dict[str, Any],
        example_posts: Optional[List[str]] = None,
        iteration: int = 1,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Review a LinkedIn post and provide feedback.

        Args:
            post: The post to review
            profile_analysis: Profile analysis results
            topic: Topic information
            example_posts: Optional list of real posts to compare style against
            iteration: Current iteration number (1-based)
            max_iterations: Maximum number of iterations allowed

        Returns:
            Dictionary with approval status and feedback
        """
        logger.info(f"Reviewing post for quality and authenticity (iteration {iteration}/{max_iterations})")

        system_prompt = self._get_system_prompt(profile_analysis, example_posts, iteration, max_iterations)
        user_prompt = self._get_user_prompt(post, topic, iteration, max_iterations)

        response = await self.call_openai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="gpt-4o",
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # Parse response
        result = json.loads(response)

        is_approved = result.get("approved", False)
        logger.info(f"Post {'APPROVED' if is_approved else 'NEEDS REVISION'}")

        return result

    def _get_system_prompt(self, profile_analysis: Dict[str, Any], example_posts: Optional[List[str]] = None, iteration: int = 1, max_iterations: int = 3) -> str:
        """Get system prompt for critic."""
        writing_style = profile_analysis.get("writing_style", {})
        linguistic = profile_analysis.get("linguistic_fingerprint", {})
        tone_analysis = profile_analysis.get("tone_analysis", {})

        # Build example posts section for style comparison
        examples_section = ""
        if example_posts and len(example_posts) > 0:
            examples_section = "\n\n**ECHTE POSTS DER PERSON (VERGLEICHE DEN STIL!):**\n"
            for i, post in enumerate(example_posts, 1):
                # Truncate very long posts
                post_text = post[:1200] + "..." if len(post) > 1200 else post
                examples_section += f"\n--- Echtes Beispiel {i} ---\n{post_text}\n"
            examples_section += "\n--- Ende Beispiele ---\n"

        # Iteration-aware guidance
        iteration_guidance = ""
        if iteration == 1:
            iteration_guidance = """
**ERSTE ITERATION - Fokus auf die WICHTIGSTEN Verbesserungen:**
- Konzentriere dich auf maximal 2-3 kritische Punkte
- Gib SEHR SPEZIFISCHE Änderungsanweisungen (z.B. "Ändere den Hook von 'X' zu 'Y'")
- Kleine Stilnuancen können später optimiert werden"""
        elif iteration == max_iterations:
            iteration_guidance = """
**LETZTE ITERATION - Sei WOHLWOLLEND bei der Bewertung:**
- Der Post wurde bereits überarbeitet
- Akzeptiere den Post wenn er GRUNDSÄTZLICH gut ist (Score >= 80)
- Kleine Imperfektionen sind OK - kein Post ist perfekt
- Bewerte ob der Post VERÖFFENTLICHBAR ist, nicht ob er PERFEKT ist"""
        else:
            iteration_guidance = f"""
**ITERATION {iteration}/{max_iterations} - Fortschritt anerkennen:**
- Prüfe ob vorherige Kritikpunkte umgesetzt wurden
- Fokussiere auf verbleibende Verbesserungen
- Gib wieder SPEZIFISCHE Änderungsanweisungen"""

        return f"""Du bist ein erfahrener LinkedIn-Content-Editor.

Deine Aufgabe: Posts bewerten und KONKRETE, UMSETZBARE Verbesserungen vorschlagen.
{examples_section}
{iteration_guidance}

**REFERENZ-PROFIL:**
- Tonalität: {tone_analysis.get('primary_tone', 'Professionell')}
- Perspektive: {writing_style.get('perspective', 'Ich')}
- Ansprache: {writing_style.get('form_of_address', 'Du')}
- Energie-Level: {linguistic.get('energy_level', 7)}/10

**BEWERTUNGSKRITERIEN (100 Punkte total):**

1. **Authentizität & Stil (40 Punkte)**
   - Klingt natürlich und menschlich (nicht wie KI)
   - Passt zur Tonalität der Person
   - Keine KI-Klischees ("In der heutigen Zeit", "Tauchen Sie ein", etc.)

2. **Content-Qualität (35 Punkte)**
   - Starker, aufmerksamkeitsstarker Hook
   - Klarer Mehrwert für die Zielgruppe
   - Gute Struktur und Lesefluss
   - Passender CTA

3. **Technische Umsetzung (25 Punkte)**
   - Richtige Perspektive und Ansprache
   - Angemessene Länge
   - Korrekte Formatierung

**APPROVAL-SCHWELLEN:**
- >= 85 Punkte: APPROVED (veröffentlichungsreif)
- 75-84 Punkte: Fast fertig, kleine Anpassungen
- < 75 Punkte: Überarbeitung nötig

**WICHTIG FÜR DEIN FEEDBACK:**
- Gib EXAKTE Formulierungsvorschläge (nicht "verbessere den Hook" sondern "Ändere 'X' zu 'Y'")
- Maximal 3 Verbesserungspunkte pro Iteration
- Erkenne Verbesserungen an wenn der Post überarbeitet wurde

Antworte als JSON."""

    def _get_user_prompt(self, post: str, topic: Dict[str, Any], iteration: int = 1, max_iterations: int = 3) -> str:
        """Get user prompt for critic."""
        iteration_note = ""
        if iteration > 1:
            iteration_note = f"\n**HINWEIS:** Dies ist Iteration {iteration} von {max_iterations}. Der Post wurde bereits überarbeitet.\n"
        if iteration == max_iterations:
            iteration_note += "**LETZTE CHANCE:** Bewerte großzügig - approve wenn der Post grundsätzlich gut ist (>= 80 Punkte).\n"

        return f"""Bewerte diesen LinkedIn-Post:
{iteration_note}
**THEMA:** {topic.get('title', 'Unknown')}

**POST:**
{post}

---

Antworte im JSON-Format:

{{
  "approved": true/false,
  "overall_score": 0-100,
  "scores": {{
    "authenticity_and_style": 0-40,
    "content_quality": 0-35,
    "technical_execution": 0-25
  }},
  "strengths": ["Stärke 1", "Stärke 2"],
  "improvements": ["Verbesserung 1", "Verbesserung 2"],
  "feedback": "Kurze Zusammenfassung",
  "specific_changes": [
    {{
      "original": "Exakter Text aus dem Post der geändert werden soll",
      "replacement": "Der neue vorgeschlagene Text",
      "reason": "Warum diese Änderung"
    }}
  ]
}}

WICHTIG bei specific_changes:
- Gib EXAKTE Textstellen an die geändert werden sollen
- Maximal 3 Changes pro Iteration
- Der "original" Text muss EXAKT im Post vorkommen"""
