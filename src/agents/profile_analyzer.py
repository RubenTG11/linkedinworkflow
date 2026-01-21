"""Profile analyzer agent."""
import json
from typing import Dict, Any, List
from loguru import logger

from src.agents.base import BaseAgent
from src.database.models import LinkedInProfile, LinkedInPost


class ProfileAnalyzerAgent(BaseAgent):
    """Agent for analyzing LinkedIn profiles and extracting writing patterns."""

    def __init__(self):
        """Initialize profile analyzer agent."""
        super().__init__("ProfileAnalyzer")

    async def process(
        self,
        profile: LinkedInProfile,
        posts: List[LinkedInPost],
        customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze LinkedIn profile and extract writing patterns.

        Args:
            profile: LinkedIn profile data
            posts: List of LinkedIn posts
            customer_data: Additional customer data from input file

        Returns:
            Comprehensive profile analysis
        """
        logger.info(f"Analyzing profile for: {profile.name}")

        # Prepare analysis data
        profile_summary = {
            "name": profile.name,
            "headline": profile.headline,
            "summary": profile.summary,
            "industry": profile.industry,
            "location": profile.location
        }

        # Prepare posts with engagement data - use up to 30 posts
        posts_with_engagement = self._prepare_posts_for_analysis(posts[:15])

        # Also identify top performing posts by engagement
        top_posts = self._get_top_performing_posts(posts, limit=5)

        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(profile_summary, posts_with_engagement, top_posts, customer_data)

        response = await self.call_openai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="gpt-4o",
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # Parse JSON response
        analysis = json.loads(response)
        logger.info("Profile analysis completed successfully")

        return analysis

    def _prepare_posts_for_analysis(self, posts: List[LinkedInPost]) -> List[Dict[str, Any]]:
        """Prepare posts with engagement data for analysis."""
        prepared = []
        for i, post in enumerate(posts):
            if not post.post_text:
                continue
            prepared.append({
                "index": i + 1,
                "text": post.post_text,
                "likes": post.likes or 0,
                "comments": post.comments or 0,
                "shares": post.shares or 0,
                "engagement_total": (post.likes or 0) + (post.comments or 0) * 2 + (post.shares or 0) * 3
            })
        return prepared

    def _get_top_performing_posts(self, posts: List[LinkedInPost], limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing posts by engagement."""
        posts_with_engagement = []
        for post in posts:
            if not post.post_text or len(post.post_text) < 50:
                continue
            engagement = (post.likes or 0) + (post.comments or 0) * 2 + (post.shares or 0) * 3
            posts_with_engagement.append({
                "text": post.post_text,
                "likes": post.likes or 0,
                "comments": post.comments or 0,
                "shares": post.shares or 0,
                "engagement_score": engagement
            })

        # Sort by engagement and return top posts
        sorted_posts = sorted(posts_with_engagement, key=lambda x: x["engagement_score"], reverse=True)
        return sorted_posts[:limit]

    def _get_system_prompt(self) -> str:
        """Get system prompt for profile analysis."""
        return """Du bist ein hochspezialisierter AI-Analyst für LinkedIn-Profile und Content-Strategie.

Deine Aufgabe ist es, aus LinkedIn-Profildaten und Posts ein umfassendes Content-Analyse-Profil zu erstellen.

Das Profil soll folgende Dimensionen analysieren:

1. **Schreibstil & Tonalität**
   - Wie schreibt die Person? (formal, locker, inspirierend, provokativ, etc.)
   - Welche Perspektive wird genutzt? (Ich, Wir, Man)
   - Wie ist die Ansprache? (Du, Sie, neutral)
   - Satzdynamik und Rhythmus

2. **Linguistischer Fingerabdruck**
   - Energielevel (1-10 Skala)
   - Nutzung von GROSSBUCHSTABEN zur Betonung
   - Besondere Satzzeichen-Muster
   - Signature Phrases (wiederkehrende Ausdrücke)
   - Erzähl-Anker (Storytelling-Elemente)

3. **Themen & Expertise**
   - Hauptthemen über die geschrieben wird
   - Zielgruppe und deren Schmerzpunkte
   - Expertise-Level
   - Content-Säulen

4. **Visuelle Muster**
   - Emoji-Nutzung (welche, wo, wie oft)
   - Unicode-Formatierung (fett, kursiv)
   - Strukturierung (Absätze, Listen, etc.)

5. **Audience Insights**
   - Wer ist die Zielgruppe?
   - Welche Probleme werden adressiert?
   - Welcher Mehrwert wird geboten?

Gib deine Analyse als strukturiertes JSON zurück."""

    def _get_user_prompt(
        self,
        profile_summary: Dict[str, Any],
        posts_with_engagement: List[Dict[str, Any]],
        top_posts: List[Dict[str, Any]],
        customer_data: Dict[str, Any]
    ) -> str:
        """Get user prompt with data for analysis."""
        # Format all posts with engagement data
        all_posts_text = ""
        for post in posts_with_engagement:
            all_posts_text += f"\n--- Post {post['index']} (Likes: {post['likes']}, Comments: {post['comments']}, Shares: {post['shares']}) ---\n"
            all_posts_text += post['text'][:2000]  # Limit each post to 2000 chars
            all_posts_text += "\n"

        # Format top performing posts
        top_posts_text = ""
        if top_posts:
            for i, post in enumerate(top_posts, 1):
                top_posts_text += f"\n--- TOP POST {i} (Engagement Score: {post['engagement_score']}, Likes: {post['likes']}, Comments: {post['comments']}) ---\n"
                top_posts_text += post['text'][:2000]
                top_posts_text += "\n"

        return f"""Bitte analysiere folgendes LinkedIn-Profil BASIEREND AUF DEN ECHTEN POSTS:

**PROFIL-INFORMATIONEN:**
- Name: {profile_summary.get('name', 'N/A')}
- Headline: {profile_summary.get('headline', 'N/A')}
- Branche: {profile_summary.get('industry', 'N/A')}
- Location: {profile_summary.get('location', 'N/A')}
- Summary: {profile_summary.get('summary', 'N/A')}

**ZUSÄTZLICHE KUNDENDATEN (Persona, Style Guide, etc.):**
{json.dumps(customer_data, indent=2, ensure_ascii=False)}

**TOP-PERFORMING POSTS (die erfolgreichsten Posts - ANALYSIERE DIESE BESONDERS GENAU!):**
{top_posts_text if top_posts_text else "Keine Engagement-Daten verfügbar"}

**ALLE POSTS ({len(posts_with_engagement)} Posts mit Engagement-Daten):**
{all_posts_text}

---

WICHTIG: Analysiere die ECHTEN POSTS sehr genau! Deine Analyse muss auf den tatsächlichen Mustern basieren, nicht auf Annahmen.

Achte besonders auf:
1. Die TOP-PERFORMING Posts - was macht sie erfolgreich?
2. Wiederkehrende Phrasen und Formulierungen
3. Wie beginnen die Posts (Hooks)?
4. Wie enden die Posts (CTAs)?
5. Emoji-Verwendung (welche, wo, wie oft)
6. Länge und Struktur der Absätze

Erstelle eine umfassende Analyse im folgenden JSON-Format:

{{
  "writing_style": {{
    "tone": "Beschreibung der Tonalität basierend auf den echten Posts",
    "perspective": "Ich/Wir/Man/Gemischt - mit Beispielen aus den Posts",
    "form_of_address": "Du/Sie/Neutral - wie spricht die Person die Leser an?",
    "sentence_dynamics": "Kurze Sätze? Lange Sätze? Mischung? Fragen?",
    "average_post_length": "Kurz/Mittel/Lang",
    "average_word_count": 0
  }},
  "linguistic_fingerprint": {{
    "energy_level": 0,
    "shouting_usage": "Beschreibung mit konkreten Beispielen aus den Posts",
    "punctuation_patterns": "Beschreibung (!!!, ..., ?, etc.)",
    "signature_phrases": ["ECHTE Phrasen aus den Posts", "die wiederholt vorkommen"],
    "narrative_anchors": ["Storytelling-Elemente", "die die Person nutzt"]
  }},
  "tone_analysis": {{
    "primary_tone": "Haupttonalität basierend auf den Posts",
    "emotional_range": "Welche Emotionen werden angesprochen?",
    "authenticity_markers": ["Was macht den Stil einzigartig?", "Erkennbare Merkmale"]
  }},
  "topic_patterns": {{
    "main_topics": ["Hauptthemen aus den Posts"],
    "content_pillars": ["Content-Säulen"],
    "expertise_areas": ["Expertise-Bereiche"],
    "expertise_level": "Anfänger/Fortgeschritten/Experte"
  }},
  "audience_insights": {{
    "target_audience": "Wer wird angesprochen?",
    "pain_points_addressed": ["Probleme die adressiert werden"],
    "value_proposition": "Welchen Mehrwert bietet die Person?",
    "industry_context": "Branchenkontext"
  }},
  "visual_patterns": {{
    "emoji_usage": {{
      "emojis": ["Liste der tatsächlich verwendeten Emojis"],
      "placement": "Anfang/Ende/Inline/Zwischen Absätzen",
      "frequency": "Selten/Mittel/Häufig - pro Post durchschnittlich X"
    }},
    "unicode_formatting": "Wird ✓, →, •, 𝗙𝗲𝘁𝘁 etc. verwendet? Wo?",
    "structure_preferences": "Absätze/Listen/Einzeiler/Nummeriert"
  }},
  "content_strategy": {{
    "hook_patterns": "Wie werden Posts KONKRET eröffnet? Beispiele!",
    "cta_style": "Wie sehen die CTAs aus? Frage? Aufforderung? Keine?",
    "storytelling_approach": "Persönliche Geschichten? Metaphern? Case Studies?",
    "post_structure": "Hook → Body → CTA? Oder anders?"
  }},
  "best_performing_patterns": {{
    "what_works": "Was machen die Top-Posts anders/besser?",
    "successful_hooks": ["Beispiel-Hooks aus Top-Posts"],
    "engagement_drivers": ["Was treibt Engagement?"]
  }}
}}

Sei KONKRET und nutze ECHTE BEISPIELE aus den Posts!"""
