"""Writer agent for creating LinkedIn posts."""
import random
from typing import Dict, Any, Optional, List
from loguru import logger

from src.agents.base import BaseAgent


class WriterAgent(BaseAgent):
    """Agent for writing LinkedIn posts based on profile analysis."""

    def __init__(self):
        """Initialize writer agent."""
        super().__init__("Writer")

    async def process(
        self,
        topic: Dict[str, Any],
        profile_analysis: Dict[str, Any],
        feedback: Optional[str] = None,
        previous_version: Optional[str] = None,
        example_posts: Optional[List[str]] = None,
        critic_result: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Write a LinkedIn post.

        Args:
            topic: Topic dictionary with title, fact, relevance
            profile_analysis: Profile analysis results
            feedback: Optional feedback from critic (text summary)
            previous_version: Optional previous version of the post
            example_posts: Optional list of real posts from the customer to use as style reference
            critic_result: Optional full critic result with specific_changes

        Returns:
            Written LinkedIn post
        """
        if feedback and previous_version:
            logger.info(f"Revising post based on critic feedback")
        else:
            logger.info(f"Writing initial post for topic: {topic.get('title', 'Unknown')}")

        # Select 2-3 random example posts if provided
        selected_examples = []
        if example_posts and len(example_posts) > 0:
            num_examples = min(3, len(example_posts))
            selected_examples = random.sample(example_posts, num_examples)
            logger.info(f"Using {len(selected_examples)} example posts as style reference")

        system_prompt = self._get_system_prompt(profile_analysis, selected_examples)
        user_prompt = self._get_user_prompt(topic, feedback, previous_version, critic_result)

        # Lower temperature for more consistent style matching
        post = await self.call_openai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="gpt-4o",
            temperature=0.6
        )

        logger.info("Post written successfully")
        return post.strip()

    def _get_system_prompt(self, profile_analysis: Dict[str, Any], example_posts: List[str] = None) -> str:
        """Get system prompt for writer."""
        # Extract key profile information
        writing_style = profile_analysis.get("writing_style", {})
        linguistic = profile_analysis.get("linguistic_fingerprint", {})
        tone_analysis = profile_analysis.get("tone_analysis", {})
        visual = profile_analysis.get("visual_patterns", {})
        content_strategy = profile_analysis.get("content_strategy", {})
        audience = profile_analysis.get("audience_insights", {})

        # Build example posts section
        examples_section = ""
        if example_posts and len(example_posts) > 0:
            examples_section = "\n\n**ECHTE BEISPIEL-POSTS DER PERSON (IMITIERE DIESEN STIL!):**\n"
            for i, post in enumerate(example_posts, 1):
                # Truncate very long posts
                post_text = post[:1500] + "..." if len(post) > 1500 else post
                examples_section += f"\n--- Beispiel {i} ---\n{post_text}\n"
            examples_section += "\n--- Ende Beispiele ---\n"
            examples_section += "\nANALYSIERE diese Beispiele genau und imitiere:\n"
            examples_section += "- Die exakte Satzstruktur und Länge\n"
            examples_section += "- Die Art der Hooks und CTAs\n"
            examples_section += "- Den Tonfall und die Energie\n"
            examples_section += "- Die Emoji-Verwendung und Formatierung\n"

        return f"""Du bist ein erstklassiger Ghostwriter für LinkedIn-Posts.

Deine Aufgabe ist es, Posts zu schreiben, die EXAKT so klingen wie der digitale Zwilling der Person.
{examples_section}
**SCHREIBSTIL:**
- Tonalität: {tone_analysis.get('primary_tone', 'Professionell und authentisch')}
- Perspektive: {writing_style.get('perspective', 'Ich-Perspektive')}
- Ansprache: {writing_style.get('form_of_address', 'Du')}
- Satzdynamik: {writing_style.get('sentence_dynamics', 'Variierend')}
- Post-Länge: {writing_style.get('average_post_length', 'Mittel')} (~{writing_style.get('average_word_count', 300)} Wörter)

**LINGUISTISCHER FINGERABDRUCK:**
- Energie-Level: {linguistic.get('energy_level', 7)}/10
- Großbuchstaben zur Betonung: {linguistic.get('shouting_usage', 'Dezent einsetzen')}
- Satzzeichen: {linguistic.get('punctuation_patterns', 'Standard')}
- Signature Phrases: {', '.join(linguistic.get('signature_phrases', []))}
- Erzähl-Anker: {', '.join(linguistic.get('narrative_anchors', []))}

**VISUELLE ELEMENTE:**
- Emojis: {visual.get('emoji_usage', {}).get('emojis', [])} | Platzierung: {visual.get('emoji_usage', {}).get('placement', 'Ende')} | Häufigkeit: {visual.get('emoji_usage', {}).get('frequency', 'Mittel')}
- Unicode-Formatierung: {visual.get('unicode_formatting', 'Für wichtige Begriffe')}
- Struktur: {visual.get('structure_preferences', 'Kurze Absätze')}

**CONTENT-STRATEGIE:**
- Hook-Muster: {content_strategy.get('hook_patterns', 'Provokative Frage oder starke Aussage')}
- CTA-Stil: {content_strategy.get('cta_style', 'Zum Dialog einladen')}
- Storytelling: {content_strategy.get('storytelling_approach', 'Persönliche Anekdoten')}

**ZIELGRUPPE:**
- Audience: {audience.get('target_audience', 'Professionals')}
- Pain Points: {', '.join(audience.get('pain_points_addressed', []))}
- Value Proposition: {audience.get('value_proposition', 'Mehrwert bieten')}

**WICHTIGE REGELN:**
1. Schreibe AUTHENTISCH im Stil der Person - nutze die Beispiel-Posts als Referenz!
2. Nutze die signature phrases ORGANISCH (nicht erzwungen)
3. Halte die Energie-Level bei {linguistic.get('energy_level', 7)}/10
4. Beginne direkt mit dem Hook - keine Meta-Kommentare
5. Der Post soll SOFORT veröffentlichbar sein
6. KOPIERE NICHT die Beispiele - imitiere nur den STIL!

Starte direkt mit dem Post - keine Einleitung, kein "Hier ist der Post"."""

    def _get_user_prompt(
        self,
        topic: Dict[str, Any],
        feedback: Optional[str] = None,
        previous_version: Optional[str] = None,
        critic_result: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get user prompt for writer."""
        if feedback and previous_version:
            # Build specific changes section
            specific_changes_text = ""
            if critic_result and critic_result.get("specific_changes"):
                specific_changes_text = "\n**KONKRETE ÄNDERUNGEN (FÜHRE DIESE EXAKT DURCH!):**\n"
                for i, change in enumerate(critic_result["specific_changes"], 1):
                    specific_changes_text += f"\n{i}. ERSETZE:\n"
                    specific_changes_text += f"   \"{change.get('original', '')}\"\n"
                    specific_changes_text += f"   MIT:\n"
                    specific_changes_text += f"   \"{change.get('replacement', '')}\"\n"
                    if change.get('reason'):
                        specific_changes_text += f"   (Grund: {change.get('reason')})\n"

            # Build improvements section
            improvements_text = ""
            if critic_result and critic_result.get("improvements"):
                improvements_text = "\n**WEITERE VERBESSERUNGEN:**\n"
                for imp in critic_result["improvements"]:
                    improvements_text += f"- {imp}\n"

            # Revision mode with structured feedback
            return f"""ÜBERARBEITE den Post basierend auf dem Kritiker-Feedback.

**VORHERIGE VERSION:**
{previous_version}

**AKTUELLER SCORE:** {critic_result.get('overall_score', 'N/A')}/100

**FEEDBACK:**
{feedback}
{specific_changes_text}
{improvements_text}
**DEINE AUFGABE:**
1. Führe die konkreten Änderungen EXAKT durch
2. Behalte alles bei was GUT bewertet wurde
3. Der überarbeitete Post soll mindestens 85 Punkte erreichen

Gib NUR den überarbeiteten Post zurück - keine Kommentare."""

        else:
            # Initial writing mode
            return f"""Schreibe einen LinkedIn-Post zu folgendem Thema:

**THEMA:** {topic.get('title', 'Unbekanntes Thema')}

**KATEGORIE:** {topic.get('category', 'Allgemein')}

**KERN-FAKT / INHALT:**
{topic.get('fact', topic.get('description', ''))}

**WARUM RELEVANT:**
{topic.get('relevance', 'Aktuelles Thema für die Zielgruppe')}

**AUFGABE:**
Schreibe einen authentischen LinkedIn-Post, der:
1. Mit einem STARKEN, unerwarteten Hook beginnt (keine Floskel!)
2. Den Fakt/das Thema aufgreift und Mehrwert bietet
3. Eine persönliche Note oder Meinung enthält
4. Mit einem passenden CTA endet

WICHTIG:
- Vermeide KI-typische Formulierungen ("In der heutigen Zeit", "Tauchen Sie ein", etc.)
- Schreibe natürlich und menschlich
- Der Post soll SOFORT 85+ Punkte im Review erreichen

Gib NUR den fertigen Post zurück."""
