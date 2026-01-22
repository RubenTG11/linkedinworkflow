"""Post type analyzer agent for creating intensive analysis per post type."""
import json
import re
from typing import Dict, Any, List
from loguru import logger

from src.agents.base import BaseAgent
from src.database.models import LinkedInPost, PostType


class PostTypeAnalyzerAgent(BaseAgent):
    """Agent for analyzing post types based on their classified posts."""

    MIN_POSTS_FOR_ANALYSIS = 3  # Minimum posts needed for meaningful analysis

    def __init__(self):
        """Initialize post type analyzer agent."""
        super().__init__("PostTypeAnalyzer")

    async def process(
        self,
        post_type: PostType,
        posts: List[LinkedInPost]
    ) -> Dict[str, Any]:
        """
        Analyze a post type based on its posts.

        Args:
            post_type: The post type to analyze
            posts: Posts belonging to this type

        Returns:
            Analysis dictionary with patterns and insights
        """
        if len(posts) < self.MIN_POSTS_FOR_ANALYSIS:
            logger.warning(f"Not enough posts for analysis: {len(posts)} < {self.MIN_POSTS_FOR_ANALYSIS}")
            return {
                "error": f"Mindestens {self.MIN_POSTS_FOR_ANALYSIS} Posts benötigt",
                "post_count": len(posts),
                "sufficient_data": False
            }

        logger.info(f"Analyzing post type '{post_type.name}' with {len(posts)} posts")

        # Prepare posts for analysis
        posts_text = self._prepare_posts_for_analysis(posts)

        # Get comprehensive analysis from LLM
        analysis = await self._analyze_posts(post_type, posts_text, len(posts))

        # Add metadata
        analysis["post_count"] = len(posts)
        analysis["sufficient_data"] = True
        analysis["post_type_name"] = post_type.name

        logger.info(f"Analysis complete for '{post_type.name}'")
        return analysis

    def _prepare_posts_for_analysis(self, posts: List[LinkedInPost]) -> str:
        """Prepare posts text for analysis."""
        posts_sections = []
        for i, post in enumerate(posts, 1):
            # Include full post text
            posts_sections.append(f"=== POST {i} ===\n{post.post_text}\n=== ENDE POST {i} ===")
        return "\n\n".join(posts_sections)

    async def _analyze_posts(
        self,
        post_type: PostType,
        posts_text: str,
        post_count: int
    ) -> Dict[str, Any]:
        """Run comprehensive analysis on posts."""

        system_prompt = """Du bist ein erfahrener LinkedIn Content-Analyst und Ghostwriter-Coach.
Deine Aufgabe ist es, Muster und Stilelemente aus einer Sammlung von Posts zu extrahieren,
um einen "Styleguide" für diesen Post-Typ zu erstellen.

Sei SEHR SPEZIFISCH und nutze ECHTE BEISPIELE aus den Posts!
Keine generischen Beschreibungen - immer konkrete Auszüge und Formulierungen.

Antworte im JSON-Format."""

        user_prompt = f"""Analysiere die folgenden {post_count} Posts vom Typ "{post_type.name}".
{f'Beschreibung: {post_type.description}' if post_type.description else ''}

=== DIE POSTS ===
{posts_text}

=== DEINE ANALYSE ===

Erstelle eine detaillierte Analyse im folgenden JSON-Format:

{{
  "structure_patterns": {{
    "typical_structure": "Beschreibe die typische Struktur (z.B. Hook → Problem → Lösung → CTA)",
    "paragraph_count": "Typische Anzahl Absätze",
    "paragraph_length": "Typische Absatzlänge in Worten",
    "uses_lists": true/false,
    "list_style": "Wenn Listen: Wie werden sie formatiert? (Bullets, Nummern, Emojis)",
    "structure_template": "Eine Vorlage für die Struktur"
  }},

  "language_style": {{
    "tone": "Haupttonalität (z.B. inspirierend, sachlich, provokativ)",
    "secondary_tones": ["Weitere Tonalitäten"],
    "perspective": "Ich-Perspektive, Du-Ansprache, Wir-Form?",
    "energy_level": 1-10,
    "formality": "formell/informell/mix",
    "sentence_types": "Kurz und knackig vs. ausführlich vs. mix",
    "typical_sentence_starters": ["Echte Beispiele wie Sätze beginnen"],
    "signature_phrases": ["Wiederkehrende Formulierungen"]
  }},

  "hooks": {{
    "hook_types": ["Welche Hook-Arten werden verwendet (Frage, Statement, Statistik, Story...)"],
    "real_examples": [
      {{
        "hook": "Der genaue Hook-Text",
        "type": "Art des Hooks",
        "why_effective": "Warum funktioniert er?"
      }}
    ],
    "hook_patterns": ["Muster die sich wiederholen"],
    "average_hook_length": "Wie lang sind Hooks typischerweise?"
  }},

  "ctas": {{
    "cta_types": ["Welche CTA-Arten (Frage, Aufforderung, Teilen-Bitte...)"],
    "real_examples": [
      {{
        "cta": "Der genaue CTA-Text",
        "type": "Art des CTAs"
      }}
    ],
    "cta_position": "Wo steht der CTA typischerweise?",
    "cta_intensity": "Wie direkt/stark ist der CTA?"
  }},

  "visual_patterns": {{
    "emoji_usage": {{
      "frequency": "hoch/mittel/niedrig/keine",
      "typical_emojis": ["Die häufigsten Emojis"],
      "placement": "Wo werden Emojis platziert?",
      "purpose": "Wofür werden sie genutzt?"
    }},
    "line_breaks": "Wie werden Absätze/Zeilenumbrüche genutzt?",
    "formatting": "Unicode-Fett, Großbuchstaben, Sonderzeichen?",
    "whitespace": "Viel/wenig Whitespace?"
  }},

  "length_patterns": {{
    "average_words": "Durchschnittliche Wortanzahl",
    "range": "Von-bis Wortanzahl",
    "ideal_length": "Empfohlene Länge für diesen Typ"
  }},

  "recurring_elements": {{
    "phrases": ["Wiederkehrende Phrasen und Formulierungen"],
    "transitions": ["Typische Übergänge zwischen Absätzen"],
    "closings": ["Typische Schlussformulierungen vor dem CTA"]
  }},

  "content_focus": {{
    "main_themes": ["Hauptthemen dieses Post-Typs"],
    "value_proposition": "Welchen Mehrwert bieten diese Posts?",
    "target_emotion": "Welche Emotion soll beim Leser ausgelöst werden?"
  }},

  "writing_guidelines": {{
    "dos": ["5-7 konkrete Empfehlungen was man TUN sollte"],
    "donts": ["3-5 konkrete Dinge die man VERMEIDEN sollte"],
    "key_success_factors": ["Was macht Posts dieses Typs erfolgreich?"]
  }}
}}

WICHTIG:
- Nutze ECHTE Textauszüge aus den Posts als Beispiele!
- Sei spezifisch, nicht generisch
- Wenn ein Muster nur in 1-2 Posts vorkommt, erwähne es trotzdem aber markiere es als "vereinzelt"
- Alle Beispiele müssen aus den gegebenen Posts stammen"""

        try:
            response = await self.call_openai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model="gpt-4o",
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            analysis = json.loads(response)
            return analysis

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {
                "error": str(e),
                "sufficient_data": True,
                "post_count": post_count
            }

    async def analyze_multiple_types(
        self,
        post_types_with_posts: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze multiple post types.

        Args:
            post_types_with_posts: List of dicts with 'post_type' and 'posts' keys

        Returns:
            Dictionary mapping post_type_id to analysis
        """
        results = {}

        for item in post_types_with_posts:
            post_type = item["post_type"]
            posts = item["posts"]

            try:
                analysis = await self.process(post_type, posts)
                results[str(post_type.id)] = analysis
            except Exception as e:
                logger.error(f"Failed to analyze post type {post_type.name}: {e}")
                results[str(post_type.id)] = {
                    "error": str(e),
                    "sufficient_data": False
                }

        return results

    def get_writing_prompt_section(self, analysis: Dict[str, Any]) -> str:
        """
        Generate a prompt section for the writer based on the analysis.

        Args:
            analysis: The post type analysis

        Returns:
            Formatted string for inclusion in writer prompts
        """
        if not analysis.get("sufficient_data"):
            return ""

        sections = []

        # Structure
        if structure := analysis.get("structure_patterns"):
            sections.append(f"""
STRUKTUR FÜR DIESEN POST-TYP:
- Typische Struktur: {structure.get('typical_structure', 'Standard')}
- Absätze: {structure.get('paragraph_count', '3-5')} Absätze
- Listen: {'Ja' if structure.get('uses_lists') else 'Nein'}
{f"- Listen-Stil: {structure.get('list_style')}" if structure.get('uses_lists') else ''}
""")

        # Language style
        if style := analysis.get("language_style"):
            sections.append(f"""
SPRACH-STIL:
- Tonalität: {style.get('tone', 'Professionell')}
- Perspektive: {style.get('perspective', 'Ich')}
- Energie-Level: {style.get('energy_level', 7)}/10
- Formalität: {style.get('formality', 'informell')}

Typische Satzanfänge:
{chr(10).join([f'  - "{s}"' for s in style.get('typical_sentence_starters', [])[:5]])}

Signature Phrases:
{chr(10).join([f'  - "{p}"' for p in style.get('signature_phrases', [])[:5]])}
""")

        # Hooks
        if hooks := analysis.get("hooks"):
            hook_examples = hooks.get("real_examples", [])[:3]
            hook_text = "\n".join([f'  - "{h.get("hook", "")}" ({h.get("type", "")})' for h in hook_examples])
            sections.append(f"""
HOOK-MUSTER:
Hook-Typen: {', '.join(hooks.get('hook_types', []))}

Echte Beispiele:
{hook_text}

Muster: {', '.join(hooks.get('hook_patterns', [])[:3])}
""")

        # CTAs
        if ctas := analysis.get("ctas"):
            cta_examples = ctas.get("real_examples", [])[:3]
            cta_text = "\n".join([f'  - "{c.get("cta", "")}"' for c in cta_examples])
            sections.append(f"""
CTA-MUSTER:
CTA-Typen: {', '.join(ctas.get('cta_types', []))}

Echte Beispiele:
{cta_text}

Position: {ctas.get('cta_position', 'Am Ende')}
""")

        # Visual patterns
        if visual := analysis.get("visual_patterns"):
            emoji = visual.get("emoji_usage", {})
            sections.append(f"""
VISUELLE ELEMENTE:
- Emoji-Nutzung: {emoji.get('frequency', 'mittel')}
- Typische Emojis: {' '.join(emoji.get('typical_emojis', [])[:8])}
- Platzierung: {emoji.get('placement', 'Variabel')}
- Formatierung: {visual.get('formatting', 'Standard')}
""")

        # Length
        if length := analysis.get("length_patterns"):
            sections.append(f"""
LÄNGE:
- Ideal: ca. {length.get('ideal_length', '200-300')} Wörter
- Range: {length.get('range', '150-400')} Wörter
""")

        # Guidelines
        if guidelines := analysis.get("writing_guidelines"):
            dos = guidelines.get("dos", [])[:5]
            donts = guidelines.get("donts", [])[:3]
            sections.append(f"""
WICHTIGE REGELN:
DO:
{chr(10).join([f'  ✓ {d}' for d in dos])}

DON'T:
{chr(10).join([f'  ✗ {d}' for d in donts])}
""")

        return "\n".join(sections)
