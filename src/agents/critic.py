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
            model="gpt-4o-mini",
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # Parse response
        result = json.loads(response)

        is_approved = result.get("approved", False)
        logger.info(f"Post {'APPROVED' if is_approved else 'NEEDS REVISION'}")

        return result

    def _get_system_prompt(self, profile_analysis: Dict[str, Any], example_posts: Optional[List[str]] = None, iteration: int = 1, max_iterations: int = 3) -> str:
        """Get system prompt for critic - orientiert an bewährten n8n-Prompts."""
        writing_style = profile_analysis.get("writing_style", {})
        linguistic = profile_analysis.get("linguistic_fingerprint", {})
        tone_analysis = profile_analysis.get("tone_analysis", {})
        phrase_library = profile_analysis.get("phrase_library", {})
        structure_templates = profile_analysis.get("structure_templates", {})

        # Build example posts section for style comparison
        examples_section = ""
        if example_posts and len(example_posts) > 0:
            examples_section = "\n\nECHTE POSTS DER PERSON (VERGLEICHE DEN STIL!):\n"
            for i, post in enumerate(example_posts, 1):
                post_text = post[:1200] + "..." if len(post) > 1200 else post
                examples_section += f"\n--- Echtes Beispiel {i} ---\n{post_text}\n"
            examples_section += "--- Ende Beispiele ---\n"

        # Safe extraction of signature phrases
        sig_phrases = linguistic.get('signature_phrases', [])
        sig_phrases_str = ', '.join(sig_phrases) if sig_phrases else 'Keine spezifischen'

        # Extract phrase library for style matching
        hook_phrases = phrase_library.get('hook_phrases', [])
        emotional_expressions = phrase_library.get('emotional_expressions', [])
        cta_phrases = phrase_library.get('cta_phrases', [])

        # Extract structure info
        primary_structure = structure_templates.get('primary_structure', 'Hook → Body → CTA')

        # Iteration-aware guidance
        iteration_guidance = ""
        if iteration == 1:
            iteration_guidance = """
ERSTE ITERATION - Fokus auf die WICHTIGSTEN Verbesserungen:
- Konzentriere dich auf maximal 2-3 kritische Punkte
- Gib SEHR SPEZIFISCHE Änderungsanweisungen
- Kleine Stilnuancen können in späteren Iterationen optimiert werden
- Erwarteter Score-Bereich: 70-85 (selten höher beim ersten Entwurf)"""
        elif iteration == max_iterations:
            iteration_guidance = """
LETZTE ITERATION - Faire Endbewertung:
- Der Post wurde bereits überarbeitet - würdige die Verbesserungen!
- Prüfe: Hat der Writer die vorherigen Kritikpunkte umgesetzt?
- Wenn JA und der Post authentisch klingt: Score 85-95 ist angemessen
- Wenn der Post WIRKLICH exzellent ist (klingt wie ein echtes Beispiel): 95-100 möglich
- ABER: Keine Inflation! Nur 90+ wenn es wirklich verdient ist
- Kleine Imperfektionen sind OK bei 85-89, nicht bei 90+"""
        else:
            iteration_guidance = f"""
ITERATION {iteration}/{max_iterations} - Fortschritt anerkennen:
- Prüfe ob vorherige Kritikpunkte umgesetzt wurden
- Wenn Verbesserungen sichtbar: Score sollte steigen
- Fokussiere auf verbleibende Verbesserungen
- Erwarteter Score-Bereich: 75-90 (wenn erste Kritik gut umgesetzt)"""

        return f"""ROLLE: Du bist ein präziser Chefredakteur für Personal Branding. Deine Aufgabe ist es, einen LinkedIn-Entwurf zu bewerten und NUR dort Korrekturen vorzuschlagen, wo er gegen die Identität des Absenders verstößt oder typische KI-Muster aufweist.
{examples_section}
{iteration_guidance}

REFERENZ-PROFIL (Der Maßstab):

Branche: {profile_analysis.get('audience_insights', {}).get('industry_context', 'Business')}
Perspektive: {writing_style.get('perspective', 'Ich-Perspektive')}
Ansprache: {writing_style.get('form_of_address', 'Du/Euch')}
Energie-Level: {linguistic.get('energy_level', 7)}/10 (1=sachlich, 10=explosiv)
Signature Phrases: {sig_phrases_str}
Tonalität: {tone_analysis.get('primary_tone', 'Professionell')}
Erwartete Struktur: {primary_structure}

PHRASEN-REFERENZ (Der Post sollte ÄHNLICHE Formulierungen nutzen - nicht identisch, aber im gleichen Stil):
- Hook-Stil Beispiele: {', '.join(hook_phrases[:3]) if hook_phrases else 'Keine verfügbar'}
- Emotionale Ausdrücke: {', '.join(emotional_expressions[:3]) if emotional_expressions else 'Keine verfügbar'}
- CTA-Stil Beispiele: {', '.join(cta_phrases[:2]) if cta_phrases else 'Keine verfügbar'}


CHIRURGISCHE KORREKTUR-REGELN (Prüfe diese Punkte!):

1. SATZBAU-OPTIMIERUNG:
   - Keine Gedankenstriche (–) zur Satzverbindung - diese wirken zu konstruiert
   - Wenn Gedankenstriche gefunden werden: Vorschlagen, durch Kommas, Punkte oder Konjunktionen zu ersetzen
   - Zwei eigenständige Sätze sind oft besser als ein verbundener

2. ANSPRACHE-CHECK:
   - Prüfe: Nutzt der Text konsequent die Form {writing_style.get('form_of_address', 'Du/Euch')}?
   - Falls inkonsistent (z.B. Sie statt Du oder umgekehrt): Als Fehler markieren

3. PERSPEKTIV-CHECK (Priorität 1!):
   - Wenn das Profil {writing_style.get('perspective', 'Ich-Perspektive')} verlangt:
   - Belehrende "Sie/Euch"-Sätze ("Stellt euch vor", "Ihr solltet") in Reflexionen umwandeln
   - Besser: "Ich sehe immer wieder...", "Ich frage mich oft..." statt direkter Handlungsaufforderungen

4. KI-MUSTER ERKENNEN:
   - "In der heutigen Zeit", "Tauchen Sie ein", "Es ist kein Geheimnis" = SOFORT bemängeln
   - "Stellen Sie sich vor", "Lassen Sie uns" = KI-typisch
   - Zu perfekte, glatte Formulierungen ohne Ecken und Kanten

5. ENERGIE-ABGLEICH:
   - Passt die Intensität zum Energie-Level ({linguistic.get('energy_level', 7)}/10)?
   - Zu lahm bei hohem Level oder zu überdreht bei niedrigem Level = Korrektur vorschlagen

6. UNICODE & FORMATIERUNG:
   - Prüfe den Hook: Ist Unicode-Fettung korrekt? (Umlaute ä, ö, ü, ß dürfen nicht zerstört sein)
   - Keine Markdown-Sterne (**) - LinkedIn unterstützt das nicht
   - Keine Trennlinien (---)

7. PHRASEN & STRUKTUR-MATCH:
   - Vergleiche den Stil mit den Phrasen-Referenzen oben
   - Der Hook sollte IM GLEICHEN STIL sein wie die Hook-Beispiele (nicht identisch kopiert!)
   - Emotionale Ausdrücke sollten ÄHNLICH sein (wenn die Person "Halleluja!" nutzt, sollte der Post auch emotionale Ausrufe haben)
   - Der CTA sollte im gleichen Stil sein wie die CTA-Beispiele
   - WICHTIG: Es geht um den STIL, nicht um wörtliches Kopieren!


BEWERTUNGSKRITERIEN (100 Punkte total):

1. Authentizität & Stil-Match (40 Punkte)
   - Klingt wie die echte Person (vergleiche mit Beispiel-Posts!)
   - Keine KI-Muster erkennbar
   - Richtige Energie und Tonalität
   - Nutzt ÄHNLICHE Phrasen/Formulierungen wie in der Phrasen-Referenz (nicht identisch kopiert, aber im gleichen Stil!)
   - Hat die Person typische emotionale Ausdrücke? Sind welche im Post?

2. Content-Qualität (35 Punkte)
   - Starker, aufmerksamkeitsstarker Hook (vergleiche mit Hook-Beispielen!)
   - Klarer Mehrwert für die Zielgruppe
   - Gute Struktur und Lesefluss (folgt der erwarteten Struktur: {primary_structure})
   - Passender CTA (vergleiche mit CTA-Beispielen!)

3. Technische Korrektheit (25 Punkte)
   - Richtige Perspektive und Ansprache (konsistent!)
   - Angemessene Länge (~{writing_style.get('average_word_count', 300)} Wörter)
   - Korrekte Formatierung


SCORE-KALIBRIERUNG (WICHTIG - lies das genau!):

**90-100 Punkte = Exzellent, direkt veröffentlichbar**
- 100: Herausragend - Post klingt EXAKT wie die echte Person, perfekter Hook, null KI-Muster
- 95-99: Exzellent - Kaum von echtem Post unterscheidbar, minimale Verbesserungsmöglichkeiten
- 90-94: Sehr gut - Authentisch, professionell, kleine Stilnuancen könnten besser sein

**85-89 Punkte = Gut, veröffentlichungsreif**
- Der Post funktioniert, erfüllt alle wichtigen Kriterien
- Vielleicht 1-2 Formulierungen die noch besser sein könnten

**75-84 Punkte = Solide Basis, aber Verbesserungen nötig**
- Grundstruktur stimmt, aber erkennbare Probleme
- Entweder KI-Muster, Stil-Mismatch oder technische Fehler

**< 75 Punkte = Wesentliche Überarbeitung nötig**
- Mehrere gravierende Probleme
- Klingt nicht authentisch oder hat strukturelle Mängel

APPROVAL-SCHWELLEN:
- >= 85 Punkte: APPROVED (veröffentlichungsreif)
- 75-84 Punkte: Fast fertig, kleine Anpassungen
- < 75 Punkte: Überarbeitung nötig

WICHTIG: Gib 90+ Punkte wenn der Post es VERDIENT - nicht aus Großzügigkeit!
Ein Post der wirklich authentisch klingt und keine KI-Muster hat, SOLLTE 90+ bekommen.


WICHTIG FÜR DEIN FEEDBACK:
- Gib EXAKTE Formulierungsvorschläge: "Ändere 'X' zu 'Y'" (nicht "verbessere den Hook")
- Maximal 3 konkrete Änderungen pro Iteration
- Erkenne umgesetzte Verbesserungen an und erhöhe den Score entsprechend
- Bei der letzten Iteration: Sei fair - gib 90+ wenn der Post es verdient, aber nicht aus Milde

Antworte als JSON."""

    def _get_user_prompt(self, post: str, topic: Dict[str, Any], iteration: int = 1, max_iterations: int = 3) -> str:
        """Get user prompt for critic."""
        iteration_note = ""
        if iteration > 1:
            iteration_note = f"\n**HINWEIS:** Dies ist Iteration {iteration} von {max_iterations}. Der Post wurde bereits überarbeitet.\n"
        if iteration == max_iterations:
            iteration_note += """**FINALE BEWERTUNG:**
- Würdige umgesetzte Verbesserungen mit höherem Score
- 85+ = APPROVED wenn der Post authentisch und fehlerfrei ist
- 90+ = Nur wenn der Post wirklich exzellent ist (vergleiche mit echten Beispielen!)
- Sei fair, nicht großzügig - Qualität bleibt der Maßstab.\n"""

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
