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
        customer_data: Dict[str, Any],
        example_posts: List[str] = None,
        post_type: Any = None,
        post_type_analysis: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Research new content topics.

        Args:
            profile_analysis: Profile analysis results
            existing_topics: List of already covered topics
            customer_data: Customer data (contains persona, style_guide, etc.)
            example_posts: List of the person's actual posts for style reference
            post_type: Optional PostType object for targeted research
            post_type_analysis: Optional post type analysis for context

        Returns:
            Research results with suggested topics
        """
        logger.info("Starting research for new content topics")
        if post_type:
            logger.info(f"Targeting research for post type: {post_type.name}")

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

        logger.info("Step 2: Transforming research into personalized topic ideas")
        # STEP 2: Transform raw research into PERSONALIZED topic suggestions
        transform_prompt = self._get_transform_prompt(
            raw_research=raw_research,
            target_audience=target_audience,
            persona=persona,
            content_pillars=content_pillars,
            example_posts=example_posts or [],
            existing_topics=existing_topics,
            post_type=post_type,
            post_type_analysis=post_type_analysis
        )

        response = await self.call_openai(
            system_prompt=self._get_topic_creator_system_prompt(),
            user_prompt=transform_prompt,
            model="gpt-4o",
            temperature=0.7,  # Higher for creative topic angles
            response_format={"type": "json_object"}
        )

        # Parse JSON response
        result = json.loads(response)
        suggested_topics = result.get("topics", [])

        # STEP 3: Ensure diversity - filter out similar topics
        suggested_topics = self._ensure_diversity(suggested_topics)

        # Parse research results
        research_results = {
            "raw_response": response,
            "suggested_topics": suggested_topics,
            "industry": industry,
            "target_audience": target_audience
        }

        logger.info(f"Research completed with {len(research_results['suggested_topics'])} topic suggestions")
        return research_results

    def _get_topic_creator_system_prompt(self) -> str:
        """Get system prompt for transforming research into personalized topics."""
        return """Du bist ein LinkedIn Content-Stratege, der aus Recherche-Ergebnissen KONKRETE, PERSONALISIERTE Themenvorschläge erstellt.

WICHTIG: Du erstellst KEINE Schlagzeilen oder News-Titel!
Du erstellst KONKRETE CONTENT-IDEEN mit:
- Einem klaren ANGLE (Perspektive/Blickwinkel)
- Einer konkreten HOOK-IDEE
- Einem NARRATIV das die Person erzählen könnte

Der Unterschied:
❌ SCHLECHT (Schlagzeile): "KI verändert den Arbeitsmarkt"
✅ GUT (Themenvorschlag): "Warum ich als [Rolle] plötzlich 50% meiner Zeit mit KI-Prompts verbringe - und was das für mein Team bedeutet"

❌ SCHLECHT: "Neue Studie zu Remote Work"
✅ GUT: "3 Erkenntnisse aus der Stanford Remote-Studie, die mich als Führungskraft überrascht haben"

❌ SCHLECHT: "Fachkräftemangel in der IT"
✅ GUT: "Unpopuläre Meinung: Wir haben keinen Fachkräftemangel - wir haben ein Ausbildungsproblem. Hier ist was ich damit meine..."

Deine Themenvorschläge müssen:
1. ZUR PERSON PASSEN - Klingt wie etwas das diese spezifische Person posten würde
2. EINEN KONKRETEN ANGLE HABEN - Nicht "über X schreiben" sondern "diesen spezifischen Aspekt von X aus dieser Perspektive beleuchten"
3. EINEN HOOK VORSCHLAGEN - Eine konkrete Idee wie der Post starten könnte
4. HINTERGRUND-INFOS LIEFERN - Fakten/Daten aus der Recherche die die Person nutzen kann
5. ABWECHSLUNGSREICH SEIN - Verschiedene Formate und Kategorien

Antworte als JSON."""

    def _get_system_prompt(self) -> str:
        """Get system prompt for research (legacy, kept for compatibility)."""
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

=== DEINE AUFGABE ===

Recherchiere FAKTEN, DATEN und ENTWICKLUNGEN - keine fertigen Themenvorschläge!
Ich brauche ROHDATEN die ich dann in personalisierte Content-Ideen umwandeln kann.

Für jede Entwicklung/News sammle:
1. **Was genau ist passiert?** - Konkrete Fakten, nicht Interpretationen
2. **Zahlen & Daten** - Statistiken, Prozentsätze, Beträge, Veränderungen
3. **Wer ist beteiligt?** - Unternehmen, Personen, Organisationen
4. **Wann?** - Genaues Datum oder Zeitraum
5. **Quelle** - URL oder Publikationsname
6. **Kontext** - Warum ist das relevant? Was bedeutet es?

SUCHE NACH:
✅ Neue Studien/Reports mit konkreten Zahlen
✅ Unternehmens-Entscheidungen oder -Ankündigungen
✅ Marktveränderungen mit Daten
✅ Gesetzliche/Regulatorische Änderungen
✅ Kontroverse Aussagen von Branchenführern
✅ Überraschende Statistiken oder Trends
✅ Gescheiterte Projekte oder unerwartete Erfolge

FORMAT DEINER ANTWORT:
Liefere 8-10 verschiedene Entwicklungen/News mit möglichst vielen Fakten und Zahlen.
Formatiere sie klar und strukturiert.

QUALITÄTSKRITERIEN:
✅ AKTUALITÄT: Von dieser Woche oder letzter Woche
✅ KONKRETHEIT: Echte Zahlen, Namen, Daten (nicht "Experten sagen...")
✅ VERIFIZIERBARKEIT: Echte Quelle die man prüfen kann
✅ BRANCHENRELEVANZ: Spezifisch für {industry}

❌ VERMEIDE:
- Vage Aussagen ohne Daten ("KI wird wichtiger")
- Generische Trends ohne konkreten Aufhänger
- Alte News die jeder schon kennt
- Themen ohne verifizierbare Fakten"""

    def _get_transform_prompt(
        self,
        raw_research: str,
        target_audience: str,
        persona: str,
        content_pillars: List[str],
        example_posts: List[str],
        existing_topics: List[str],
        post_type: Any = None,
        post_type_analysis: Dict[str, Any] = None
    ) -> str:
        """Transform raw research into personalized, concrete topic suggestions."""

        # Build example posts section
        examples_section = ""
        if example_posts:
            examples_section = "\n\n=== SO SCHREIBT DIESE PERSON (Beispiel-Posts) ===\n"
            for i, post in enumerate(example_posts[:5], 1):
                post_preview = post[:600] + "..." if len(post) > 600 else post
                examples_section += f"\n--- Beispiel {i} ---\n{post_preview}\n"
            examples_section += "--- Ende Beispiele ---\n"

        # Build pillars section
        pillars_text = ", ".join(content_pillars[:5]) if content_pillars else "Keine spezifischen Säulen"

        # Build existing topics section (to avoid)
        existing_text = ", ".join(existing_topics[:15]) if existing_topics else "Keine"

        # Build post type context section
        post_type_section = ""
        if post_type:
            post_type_section = f"""

=== ZIEL-POST-TYP: {post_type.name} ===
{f"Beschreibung: {post_type.description}" if post_type.description else ""}
{f"Typische Hashtags: {', '.join(post_type.identifying_hashtags[:5])}" if post_type.identifying_hashtags else ""}
{f"Keywords: {', '.join(post_type.identifying_keywords[:10])}" if post_type.identifying_keywords else ""}
"""
            if post_type.semantic_properties:
                props = post_type.semantic_properties
                if props.get("purpose"):
                    post_type_section += f"Zweck: {props['purpose']}\n"
                if props.get("typical_tone"):
                    post_type_section += f"Tonalität: {props['typical_tone']}\n"
                if props.get("target_audience"):
                    post_type_section += f"Zielgruppe: {props['target_audience']}\n"

            if post_type_analysis and post_type_analysis.get("sufficient_data"):
                post_type_section += "\n**Analyse-basierte Anforderungen:**\n"
                if hooks := post_type_analysis.get("hooks"):
                    post_type_section += f"- Hook-Typen: {', '.join(hooks.get('hook_types', [])[:3])}\n"
                if content := post_type_analysis.get("content_focus"):
                    post_type_section += f"- Hauptthemen: {', '.join(content.get('main_themes', [])[:3])}\n"
                    if content.get("target_emotion"):
                        post_type_section += f"- Ziel-Emotion: {content['target_emotion']}\n"

            post_type_section += "\n**WICHTIG:** Alle Themenvorschläge müssen zu diesem Post-Typ passen!\n"

        return f"""AUFGABE: Transformiere die Recherche-Ergebnisse in KONKRETE, PERSONALISIERTE Themenvorschläge.
{post_type_section}

=== RECHERCHE-ERGEBNISSE (Rohdaten) ===
{raw_research}

=== PERSON/EXPERTISE ===
{persona[:800] if persona else "Keine Persona definiert"}

=== CONTENT-SÄULEN DER PERSON ===
{pillars_text}
{examples_section}
=== BEREITS BEHANDELT (NICHT NOCHMAL!) ===
{existing_text}

=== DEINE AUFGABE ===

Erstelle 6-8 KONKRETE Themenvorschläge die:
1. ZU DIESER PERSON PASSEN - Basierend auf Expertise und Beispiel-Posts
2. EINEN KLAREN ANGLE HABEN - Nicht "über X schreiben" sondern eine spezifische Perspektive
3. FAKTEN AUS DER RECHERCHE NUTZEN - Konkrete Daten/Zahlen einbauen
4. ABWECHSLUNGSREICH SIND - Verschiedene Kategorien und Formate

KATEGORIEN (mindestens 3 verschiedene!):
- **Meinung/Take**: Deine Perspektive zu einem aktuellen Thema
- **Erfahrungsbericht**: "Was ich gelernt habe als..."
- **Konträr**: "Unpopuläre Meinung: ..."
- **How-To/Insight**: Konkrete Tipps basierend auf Daten
- **Story**: Persönliche Geschichte mit Business-Lesson
- **Analyse**: Daten/Trend analysiert durch deine Expertise-Brille

FORMAT DER THEMENVORSCHLÄGE:

{{
  "topics": [
    {{
      "title": "Konkreter Thementitel (kein Schlagzeilen-Stil!)",
      "category": "Meinung/Take | Erfahrungsbericht | Konträr | How-To/Insight | Story | Analyse",
      "angle": "Der spezifische Blickwinkel/die Perspektive für diesen Post",
      "hook_idea": "Konkrete Hook-Idee die zum Post passen würde (1-2 Sätze)",
      "key_facts": ["Fakt 1 aus der Recherche", "Fakt 2 mit Zahlen", "Fakt 3"],
      "why_this_person": "Warum passt dieses Thema zu DIESER Person und ihrer Expertise?",
      "source": "Quellenangabe"
    }}
  ]
}}

BEISPIEL EINES GUTEN THEMENVORSCHLAGS:
{{
  "title": "Warum ich als Tech-Lead jetzt 30% meiner Zeit mit Prompt Engineering verbringe",
  "category": "Erfahrungsbericht",
  "angle": "Persönliche Erfahrung eines Tech-Leads mit der Veränderung seiner Rolle durch KI",
  "hook_idea": "Vor einem Jahr habe ich Code geschrieben. Heute schreibe ich Prompts. Und ehrlich? Ich weiß noch nicht ob das gut oder schlecht ist.",
  "key_facts": ["GitHub Copilot wird von 92% der Entwickler genutzt (Stack Overflow 2024)", "Durchschnittliche Zeitersparnis: 55%", "Aber: Code-Review-Zeit +40%"],
  "why_this_person": "Als Tech-Lead hat die Person direkten Einblick in diese Veränderung und kann authentisch darüber berichten",
  "source": "Stack Overflow Developer Survey 2024"
}}

WICHTIG:
- Jeder Vorschlag muss sich UNTERSCHEIDEN (anderer Angle, andere Kategorie)
- Keine generischen "Die Zukunft von X" Themen
- Hook-Ideen müssen zum Stil der Beispiel-Posts passen!
- Key Facts müssen aus der Recherche stammen (keine erfundenen Zahlen)"""

    def _get_structure_prompt(
        self,
        raw_research: str,
        target_audience: str,
        persona: str = ""
    ) -> str:
        """Get prompt to structure Perplexity research into JSON (legacy)."""
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

    def _ensure_diversity(self, topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensure topic suggestions are diverse (different categories, angles).

        Args:
            topics: List of topic suggestions

        Returns:
            Filtered list with diverse topics
        """
        if len(topics) <= 3:
            return topics

        # Track categories used
        category_counts = {}
        diverse_topics = []

        for topic in topics:
            category = topic.get("category", "Unknown")

            # Allow max 2 topics per category
            if category_counts.get(category, 0) < 2:
                diverse_topics.append(topic)
                category_counts[category] = category_counts.get(category, 0) + 1

        # If we filtered too many, add back some
        if len(diverse_topics) < 5 and len(topics) >= 5:
            for topic in topics:
                if topic not in diverse_topics:
                    diverse_topics.append(topic)
                    if len(diverse_topics) >= 6:
                        break

        logger.info(f"Diversity check: {len(topics)} -> {len(diverse_topics)} topics, categories: {category_counts}")
        return diverse_topics

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
