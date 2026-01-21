"""Research agent using Perplexity."""
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List
from loguru import logger

from src.agents.base import BaseAgent


class ResearchAgent(BaseAgent):
    """Agent for researching new content topics using Perplexity."""

    def __init__(self):
        """Initialize research agent."""
        super().__init__("Researcher")

    async def process(
        self,
        profile_analysis: Dict[str, Any],
        existing_topics: List[str],
        customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Research new content topics.

        Args:
            profile_analysis: Profile analysis results
            existing_topics: List of already covered topics
            customer_data: Customer data (contains persona, style_guide, etc.)

        Returns:
            Research results with suggested topics
        """
        logger.info("Starting research for new content topics")

        # Extract key information from profile analysis
        audience_insights = profile_analysis.get("audience_insights", {})
        topic_patterns = profile_analysis.get("topic_patterns", {})

        industry = audience_insights.get("industry_context", "Business")
        target_audience = audience_insights.get("target_audience", "Professionals")
        content_pillars = topic_patterns.get("content_pillars", [])
        pain_points = audience_insights.get("pain_points_addressed", [])
        value_proposition = audience_insights.get("value_proposition", "")

        # Extract customer-specific data
        persona = customer_data.get("persona", "") if customer_data else ""

        # STEP 1: Use Perplexity for REAL internet research (has live data!)
        logger.info("Step 1: Researching with Perplexity (live internet data)")
        perplexity_prompt = self._get_perplexity_prompt(
            industry=industry,
            target_audience=target_audience,
            content_pillars=content_pillars,
            existing_topics=existing_topics,
            pain_points=pain_points,
            persona=persona
        )

        # Dynamic system prompt for variety
        system_prompts = [
            "Du bist ein investigativer Journalist. Finde die neuesten, spannendsten Entwicklungen mit harten Fakten.",
            "Du bist ein Branchen-Analyst. Identifiziere aktuelle Trends und Marktbewegungen mit konkreten Daten.",
            "Du bist ein Trend-Scout. Spüre auf, was diese Woche wirklich neu und relevant ist.",
            "Du bist ein Research-Spezialist. Finde aktuelle Studien, Statistiken und News mit Quellenangaben."
        ]

        raw_research = await self.call_perplexity(
            system_prompt=random.choice(system_prompts),
            user_prompt=perplexity_prompt,
            model="sonar-pro"
        )

        logger.info("Step 2: Structuring results with OpenAI")
        # STEP 2: Use OpenAI to structure the Perplexity results into clean JSON
        structure_prompt = self._get_structure_prompt(
            raw_research=raw_research,
            target_audience=target_audience,
            persona=persona
        )

        response = await self.call_openai(
            system_prompt="Du strukturierst Recherche-Ergebnisse in ein sauberes JSON-Format. Behalte alle Fakten, Quellen und Details bei.",
            user_prompt=structure_prompt,
            model="gpt-4o",
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # Parse JSON response
        result = json.loads(response)
        suggested_topics = result.get("topics", [])

        # Parse research results
        research_results = {
            "raw_response": response,
            "suggested_topics": suggested_topics,
            "industry": industry,
            "target_audience": target_audience
        }

        logger.info(f"Research completed with {len(research_results['suggested_topics'])} topic suggestions")
        return research_results

    def _get_system_prompt(self) -> str:
        """Get system prompt for research."""
        return """Du bist ein hochspezialisierter Trend-Analyst und Content-Researcher.

Deine Mission ist es, aktuelle, hochrelevante Content-Themen für LinkedIn zu identifizieren.

Du sollst:
1. Aktuelle Trends, News und Diskussionen der letzten 7-14 Tage recherchieren
2. Themen finden, die für die spezifische Zielgruppe relevant sind
3. Verschiedene Kategorien abdecken:
   - Aktuelle News & Studien
   - Schmerzpunkt-Lösungen
   - Konträre Trends (gegen Mainstream-Meinung)
   - Emerging Topics

Für jedes Thema sollst du bereitstellen:
- Einen prägnanten Titel
- Den Kern-Fakt (mit Daten, Quellen, Beispielen)
- Warum es relevant ist für die Zielgruppe
- Die Kategorie

Fokussiere dich auf Themen, die:
- AKTUELL sind (letzte 1-2 Wochen)
- KONKRET sind (mit Daten/Fakten belegt)
- RELEVANT sind für die Zielgruppe
- UNIQUE sind (nicht bereits behandelt)

Gib deine Antwort als JSON zurück."""

    def _get_user_prompt(
        self,
        industry: str,
        target_audience: str,
        content_pillars: List[str],
        existing_topics: List[str],
        pain_points: List[str] = None,
        value_proposition: str = "",
        persona: str = ""
    ) -> str:
        """Get user prompt for research."""
        pillars_text = ", ".join(content_pillars) if content_pillars else "Verschiedene Business-Themen"
        existing_text = ", ".join(existing_topics[:20]) if existing_topics else "Keine"
        pain_points_text = ", ".join(pain_points) if pain_points else "Nicht spezifiziert"

        # Build persona section if available
        persona_section = ""
        if persona:
            persona_section = f"""
**PERSONA DER PERSON (WICHTIG - Themen müssen zu dieser Expertise passen!):**
{persona[:800]}
"""

        return f"""Recherchiere aktuelle LinkedIn-Content-Themen für folgendes Profil:

**KONTEXT:**
- Branche: {industry}
- Zielgruppe: {target_audience}
- Content-Säulen: {pillars_text}
- Pain Points der Zielgruppe: {pain_points_text}
- Value Proposition: {value_proposition or 'Mehrwert für die Zielgruppe bieten'}
{persona_section}
**BEREITS BEHANDELTE THEMEN (diese NICHT vorschlagen):**
{existing_text}

**AUFGABE:**
Finde 5-7 verschiedene aktuelle Themen, die:
1. ZUR EXPERTISE/PERSONA der Person passen
2. Die PAIN POINTS der Zielgruppe addressieren
3. AUTHENTISCH von dieser Person kommen könnten
4. NICHT generisch oder beliebig sind

Kategorien:
1. **News-Flash**: Aktuelle Nachrichten, Studien oder Entwicklungen
2. **Schmerzpunkt-Löser**: Probleme/Diskussionen, die die Zielgruppe aktuell beschäftigen
3. **Konträrer Trend**: Entwicklungen, die gegen die herkömmliche Meinung verstoßen
4. **Emerging Topic**: Neue Trends, die gerade an Fahrt gewinnen

WICHTIG: Themen müssen zur Person passen! Ein Experte für {industry} würde keine generischen "Productivity-Tips" posten, sondern spezifische Insights aus seinem Fachgebiet.

Fokus auf deutsche/DACH-Region relevante Themen.

Gib deine Antwort im folgenden JSON-Format zurück:

{{
  "topics": [
    {{
      "title": "Prägnanter Arbeitstitel (spezifisch, nicht generisch!)",
      "category": "News-Flash / Schmerzpunkt-Löser / Konträrer Trend / Emerging Topic",
      "fact": "Detaillierte Zusammenfassung mit Daten, Fakten, Beispielen - SPEZIFISCH für diese Branche",
      "relevance": "Warum ist das für {target_audience} wichtig und warum sollte DIESE Person darüber schreiben?",
      "source": "Quellenangaben (Studien, Artikel, Statistiken)"
    }}
  ]
}}"""

    def _get_perplexity_prompt(
        self,
        industry: str,
        target_audience: str,
        content_pillars: List[str],
        existing_topics: List[str],
        pain_points: List[str] = None,
        persona: str = ""
    ) -> str:
        """Get prompt for Perplexity research (optimized for live internet search)."""
        pillars_text = ", ".join(content_pillars) if content_pillars else "Business-Themen"
        existing_text = ", ".join(existing_topics[:20]) if existing_topics else "Keine bisherigen Themen"
        pain_points_text = ", ".join(pain_points) if pain_points else "Allgemeine Business-Probleme"

        # Current date for time-specific searches
        today = datetime.now()
        date_str = today.strftime("%d. %B %Y")
        week_ago = (today - timedelta(days=7)).strftime("%d. %B %Y")

        persona_hint = ""
        if persona:
            persona_hint = f"\nEXPERTISE DER PERSON: {persona[:600]}\n"

        # Randomize the research focus for variety
        research_angles = [
            {
                "name": "Breaking News & Studien",
                "focus": "Suche nach brandneuen Studien, Reports, Umfragen oder Nachrichten",
                "examples": "Neue Statistiken, Forschungsergebnisse, Unternehmens-Announcements"
            },
            {
                "name": "Kontroverse & Debatten",
                "focus": "Suche nach aktuellen Kontroversen, Meinungsverschiedenheiten, heißen Diskussionen",
                "examples": "Polarisierende Meinungen, Kritik an Trends, unerwartete Entwicklungen"
            },
            {
                "name": "Technologie & Innovation",
                "focus": "Suche nach neuen Tools, Technologien, Methoden die gerade aufkommen",
                "examples": "Neue Software, AI-Entwicklungen, Prozess-Innovationen"
            },
            {
                "name": "Markt & Wirtschaft",
                "focus": "Suche nach wirtschaftlichen Entwicklungen, Marktveränderungen, Branchen-Shifts",
                "examples": "Fusionen, Insolvenzen, Markteintritt, Regulierungen"
            },
            {
                "name": "Menschen & Karriere",
                "focus": "Suche nach Personalien, Karriere-Trends, Arbeitsmarkt-Entwicklungen",
                "examples": "Führungswechsel, Hiring-Trends, Remote Work Updates, Skill-Demands"
            },
            {
                "name": "Fails & Learnings",
                "focus": "Suche nach öffentlichen Fehlern, Shitstorms, Lessons Learned",
                "examples": "PR-Desaster, gescheiterte Launches, öffentliche Kritik"
            }
        ]

        # Pick 3-4 random angles for this research session
        selected_angles = random.sample(research_angles, min(4, len(research_angles)))
        angles_text = "\n".join([
            f"- **{angle['name']}**: {angle['focus']} (z.B. {angle['examples']})"
            for angle in selected_angles
        ])

        # Random seed words for more variety
        seed_variations = [
            f"Was ist DIESE WOCHE ({week_ago} bis {date_str}) passiert in {industry}?",
            f"Welche BREAKING NEWS gibt es HEUTE ({date_str}) oder diese Woche in {industry}?",
            f"Was diskutiert die {industry}-Branche AKTUELL ({date_str})?",
            f"Welche NEUEN Entwicklungen gibt es seit {week_ago} in {industry}?"
        ]
        seed_question = random.choice(seed_variations)

        return f"""AKTUELLES DATUM: {date_str}

{seed_question}
{persona_hint}
KONTEXT:
- Branche: {industry}
- Zielgruppe: {target_audience}
- Themen-Fokus: {pillars_text}
- Pain Points: {pain_points_text}

RECHERCHE-SCHWERPUNKTE FÜR DIESE SESSION:
{angles_text}

⛔ BEREITS BEHANDELTE THEMEN - NICHT NOCHMAL VORSCHLAGEN:
{existing_text}

AUFGABE:
Finde 6-8 WIRKLICH AKTUELLE und SPEZIFISCHE Themen.

Für jedes Thema:
1. **Titel**: Konkreter, spezifischer Titel (nicht generisch!)
2. **Was ist passiert?**: Echte Fakten, Zahlen, Namen, Daten
3. **Wann?**: Genaues Datum wenn möglich
4. **Quelle**: URL oder Publikationsname
5. **Relevanz**: Warum sollte {target_audience} das interessieren?

QUALITÄTSKRITERIEN:
✅ Thema ist von dieser Woche oder letzter Woche
✅ Enthält konkrete Fakten/Zahlen (nicht "Experten sagen...")
✅ Hat eine echte Quelle die man prüfen kann
✅ Ist SPEZIFISCH für {industry} (keine generischen Produktivitäts-Tipps)
✅ Wurde noch NICHT in den bereits behandelten Themen erwähnt

❌ VERMEIDE:
- Generische Themen wie "Die Zukunft von X" ohne konkrete News
- Evergreen-Content ohne aktuellen Aufhänger
- Themen ohne konkrete Daten/Fakten
- Alles was älter als 2 Wochen ist"""

    def _get_structure_prompt(
        self,
        raw_research: str,
        target_audience: str,
        persona: str = ""
    ) -> str:
        """Get prompt to structure Perplexity research into JSON."""
        return f"""Strukturiere die folgenden Recherche-Ergebnisse in ein sauberes JSON-Format.

RECHERCHE-ERGEBNISSE:
{raw_research}

AUFGABE:
Extrahiere die Themen und formatiere sie als JSON. Behalte ALLE Fakten, Quellen und Details bei.

Gib das Ergebnis in diesem Format zurück:

{{
  "topics": [
    {{
      "title": "Prägnanter Titel des Themas",
      "category": "News-Flash / Schmerzpunkt-Löser / Konträrer Trend / Emerging Topic",
      "fact": "Die kompletten Fakten, Zahlen und Details aus der Recherche - NICHTS weglassen!",
      "relevance": "Warum ist das für {target_audience} wichtig?",
      "source": "Quellenangaben aus der Recherche"
    }}
  ]
}}

WICHTIG:
- Behalte ALLE Fakten und Quellen aus der Recherche
- Erfinde NICHTS dazu
- Wenn etwas unklar ist, lass es weg
- Mindestens 5 Themen wenn vorhanden"""

    def _extract_topics_from_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Extract structured topics from Perplexity response.

        Args:
            response: Raw response from Perplexity

        Returns:
            List of structured topic dictionaries
        """
        topics = []

        # Simple parsing - split by topic markers
        sections = response.split("[TITEL]:")

        for section in sections[1:]:  # Skip first empty section
            try:
                # Extract title
                title_end = section.find("[KATEGORIE]:")
                if title_end == -1:
                    title_end = section.find("\n")
                title = section[:title_end].strip()

                # Extract category
                category = ""
                if "[KATEGORIE]:" in section:
                    cat_start = section.find("[KATEGORIE]:") + len("[KATEGORIE]:")
                    cat_end = section.find("[DER FAKT]:")
                    if cat_end == -1:
                        cat_end = section.find("\n", cat_start)
                    category = section[cat_start:cat_end].strip()

                # Extract fact
                fact = ""
                if "[DER FAKT]:" in section:
                    fact_start = section.find("[DER FAKT]:") + len("[DER FAKT]:")
                    fact_end = section.find("[WARUM RELEVANT]:")
                    if fact_end == -1:
                        fact_end = section.find("[QUELLE]:")
                    if fact_end == -1:
                        fact_end = len(section)
                    fact = section[fact_start:fact_end].strip()

                # Extract relevance
                relevance = ""
                if "[WARUM RELEVANT]:" in section:
                    rel_start = section.find("[WARUM RELEVANT]:") + len("[WARUM RELEVANT]:")
                    rel_end = section.find("[QUELLE]:")
                    if rel_end == -1:
                        rel_end = len(section)
                    relevance = section[rel_start:rel_end].strip()

                if title and fact:
                    topics.append({
                        "title": title,
                        "category": category or "Allgemein",
                        "fact": fact,
                        "relevance": relevance,
                        "source": "perplexity_research"
                    })
            except Exception as e:
                logger.warning(f"Failed to parse topic section: {e}")
                continue

        return topics
