"""Writer agent for creating LinkedIn posts."""
import asyncio
import json
import random
import re
from typing import Dict, Any, Optional, List
from loguru import logger

from src.agents.base import BaseAgent
from src.config import settings


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
        critic_result: Optional[Dict[str, Any]] = None,
        learned_lessons: Optional[Dict[str, Any]] = None
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
            learned_lessons: Optional lessons learned from past critic feedback

        Returns:
            Written LinkedIn post
        """
        if feedback and previous_version:
            logger.info(f"Revising post based on critic feedback")
            # For revisions, always use single draft (feedback is specific)
            return await self._write_single_draft(
                topic=topic,
                profile_analysis=profile_analysis,
                feedback=feedback,
                previous_version=previous_version,
                example_posts=example_posts,
                critic_result=critic_result,
                learned_lessons=learned_lessons
            )
        else:
            logger.info(f"Writing initial post for topic: {topic.get('title', 'Unknown')}")

            # Select example posts - use semantic matching if enabled
            selected_examples = self._select_example_posts(topic, example_posts, profile_analysis)

            # Use Multi-Draft if enabled for initial posts
            if settings.writer_multi_draft_enabled:
                return await self._write_multi_draft(
                    topic=topic,
                    profile_analysis=profile_analysis,
                    example_posts=selected_examples,
                    learned_lessons=learned_lessons
                )
            else:
                return await self._write_single_draft(
                    topic=topic,
                    profile_analysis=profile_analysis,
                    example_posts=selected_examples,
                    learned_lessons=learned_lessons
                )

    def _select_example_posts(
        self,
        topic: Dict[str, Any],
        example_posts: Optional[List[str]],
        profile_analysis: Dict[str, Any]
    ) -> List[str]:
        """
        Select example posts - either semantically similar or random.

        Args:
            topic: The topic to write about
            example_posts: All available example posts
            profile_analysis: Profile analysis results

        Returns:
            Selected example posts (3-4 posts)
        """
        if not example_posts or len(example_posts) == 0:
            return []

        if not settings.writer_semantic_matching_enabled:
            # Fallback to random selection
            num_examples = min(3, len(example_posts))
            selected = random.sample(example_posts, num_examples)
            logger.info(f"Using {len(selected)} random example posts")
            return selected

        # Semantic matching based on keywords
        logger.info("Using semantic matching for example post selection")

        # Extract keywords from topic
        topic_text = f"{topic.get('title', '')} {topic.get('fact', '')} {topic.get('category', '')}".lower()
        topic_keywords = self._extract_keywords(topic_text)

        # Score each post by keyword overlap
        scored_posts = []
        for post in example_posts:
            post_lower = post.lower()
            score = 0
            matched_keywords = []

            for keyword in topic_keywords:
                if keyword in post_lower:
                    score += 1
                    matched_keywords.append(keyword)

            # Bonus for longer matches
            score += len(matched_keywords) * 0.5

            scored_posts.append({
                "post": post,
                "score": score,
                "matched": matched_keywords
            })

        # Sort by score (highest first)
        scored_posts.sort(key=lambda x: x["score"], reverse=True)

        # Take top 2 by relevance + 1 random (for variety)
        selected = []

        # Top 2 most relevant
        for item in scored_posts[:2]:
            if item["score"] > 0:
                selected.append(item["post"])
                logger.debug(f"Selected post (score {item['score']:.1f}, keywords: {item['matched'][:3]})")

        # Add 1 random post for variety (if not already selected)
        remaining_posts = [p["post"] for p in scored_posts[2:] if p["post"] not in selected]
        if remaining_posts and len(selected) < 3:
            random_pick = random.choice(remaining_posts)
            selected.append(random_pick)
            logger.debug("Added 1 random post for variety")

        # If we still don't have enough, fill with top scored
        while len(selected) < 3 and len(selected) < len(example_posts):
            for item in scored_posts:
                if item["post"] not in selected:
                    selected.append(item["post"])
                    break

        logger.info(f"Selected {len(selected)} example posts via semantic matching")
        return selected

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Remove common stop words
        stop_words = {
            'der', 'die', 'das', 'und', 'in', 'zu', 'den', 'von', 'für', 'mit',
            'auf', 'ist', 'im', 'sich', 'des', 'ein', 'eine', 'als', 'auch',
            'es', 'an', 'werden', 'aus', 'er', 'hat', 'dass', 'sie', 'nach',
            'wird', 'bei', 'einer', 'um', 'am', 'sind', 'noch', 'wie', 'einem',
            'über', 'so', 'zum', 'kann', 'nur', 'sein', 'ich', 'nicht', 'was',
            'oder', 'aber', 'wenn', 'ihre', 'man', 'the', 'and', 'to', 'of',
            'a', 'is', 'that', 'it', 'for', 'on', 'are', 'with', 'be', 'this',
            'was', 'have', 'from', 'your', 'you', 'we', 'our', 'mehr', 'neue',
            'neuen', 'können', 'durch', 'diese', 'dieser', 'einem', 'einen'
        }

        # Split and clean
        words = re.findall(r'\b[a-zäöüß]{3,}\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) >= 4]

        # Also extract compound words and important terms
        important_terms = re.findall(r'\b[A-Z][a-zäöüß]+(?:[A-Z][a-zäöüß]+)*\b', text)
        keywords.extend([t.lower() for t in important_terms if len(t) >= 4])

        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords[:15]  # Limit to top 15 keywords

    async def _write_multi_draft(
        self,
        topic: Dict[str, Any],
        profile_analysis: Dict[str, Any],
        example_posts: List[str],
        learned_lessons: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate multiple drafts and select the best one.

        Args:
            topic: Topic to write about
            profile_analysis: Profile analysis results
            example_posts: Example posts for style reference
            learned_lessons: Lessons learned from past feedback

        Returns:
            Best selected draft
        """
        num_drafts = min(max(settings.writer_multi_draft_count, 2), 5)  # Clamp between 2-5
        logger.info(f"Generating {num_drafts} drafts for selection")

        system_prompt = self._get_system_prompt(profile_analysis, example_posts, learned_lessons)

        # Generate drafts in parallel with different temperatures/approaches
        draft_configs = [
            {"temperature": 0.5, "approach": "fokussiert"},
            {"temperature": 0.7, "approach": "kreativ"},
            {"temperature": 0.6, "approach": "ausgewogen"},
            {"temperature": 0.8, "approach": "experimentell"},
            {"temperature": 0.55, "approach": "präzise"},
        ][:num_drafts]

        # Create draft tasks
        async def generate_draft(config: Dict, draft_num: int) -> Dict[str, Any]:
            user_prompt = self._get_user_prompt_for_draft(topic, draft_num, config["approach"])
            try:
                draft = await self.call_openai(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model="gpt-4o",
                    temperature=config["temperature"]
                )
                return {
                    "draft_num": draft_num,
                    "content": draft.strip(),
                    "approach": config["approach"],
                    "temperature": config["temperature"]
                }
            except Exception as e:
                logger.error(f"Failed to generate draft {draft_num}: {e}")
                return None

        # Run drafts in parallel
        tasks = [generate_draft(config, i + 1) for i, config in enumerate(draft_configs)]
        results = await asyncio.gather(*tasks)

        # Filter out failed drafts
        drafts = [r for r in results if r is not None]

        if not drafts:
            raise ValueError("All draft generations failed")

        if len(drafts) == 1:
            logger.warning("Only one draft succeeded, using it directly")
            return drafts[0]["content"]

        logger.info(f"Generated {len(drafts)} drafts, now selecting best one")

        # Select the best draft
        best_draft = await self._select_best_draft(drafts, topic, profile_analysis)
        return best_draft

    def _get_user_prompt_for_draft(
        self,
        topic: Dict[str, Any],
        draft_num: int,
        approach: str
    ) -> str:
        """Get user prompt with slight variations for different drafts."""
        # Different emphasis for each draft
        emphasis_variations = {
            1: "Fokussiere auf einen STARKEN, überraschenden Hook. Der erste Satz muss fesseln!",
            2: "Fokussiere auf STORYTELLING. Baue eine kleine Geschichte oder Anekdote ein.",
            3: "Fokussiere auf KONKRETEN MEHRWERT. Was lernt der Leser konkret?",
            4: "Fokussiere auf EMOTION. Sprich Gefühle und persönliche Erfahrungen an.",
            5: "Fokussiere auf PROVOKATION. Stelle eine These auf, die zum Nachdenken anregt.",
        }

        emphasis = emphasis_variations.get(draft_num, emphasis_variations[1])

        # Build enhanced topic section with new fields
        angle_section = ""
        if topic.get('angle'):
            angle_section = f"\n**ANGLE/PERSPEKTIVE:**\n{topic.get('angle')}\n"

        hook_section = ""
        if topic.get('hook_idea'):
            hook_section = f"\n**HOOK-IDEE (als Inspiration):**\n\"{topic.get('hook_idea')}\"\n"

        facts_section = ""
        key_facts = topic.get('key_facts', [])
        if key_facts and isinstance(key_facts, list) and len(key_facts) > 0:
            facts_section = "\n**KEY FACTS (nutze diese!):**\n" + "\n".join([f"- {f}" for f in key_facts]) + "\n"

        why_section = ""
        if topic.get('why_this_person'):
            why_section = f"\n**WARUM DU DARÜBER SCHREIBEN SOLLTEST:**\n{topic.get('why_this_person')}\n"

        return f"""Schreibe einen LinkedIn-Post zu folgendem Thema:

**THEMA:** {topic.get('title', 'Unbekanntes Thema')}

**KATEGORIE:** {topic.get('category', 'Allgemein')}
{angle_section}{hook_section}
**KERN-FAKT / INHALT:**
{topic.get('fact', topic.get('description', ''))}
{facts_section}
**WARUM RELEVANT:**
{topic.get('relevance', 'Aktuelles Thema für die Zielgruppe')}
{why_section}
**DEIN ANSATZ FÜR DIESEN ENTWURF ({approach}):**
{emphasis}

**AUFGABE:**
Schreibe einen authentischen LinkedIn-Post, der:
1. Mit einem STARKEN, unerwarteten Hook beginnt (nutze die Hook-Idee als Inspiration, NICHT wörtlich!)
2. Den Fakt/das Thema aufgreift und Mehrwert bietet
3. Die Key Facts einbaut wo es passt
4. Eine persönliche Note oder Meinung enthält
5. Mit einem passenden CTA endet

WICHTIG:
- Vermeide KI-typische Formulierungen ("In der heutigen Zeit", "Tauchen Sie ein", etc.)
- Schreibe natürlich und menschlich
- Der Post soll SOFORT 85+ Punkte im Review erreichen
- Die Hook-Idee ist nur INSPIRATION - mach etwas Eigenes daraus!

Gib NUR den fertigen Post zurück."""

    async def _select_best_draft(
        self,
        drafts: List[Dict[str, Any]],
        topic: Dict[str, Any],
        profile_analysis: Dict[str, Any]
    ) -> str:
        """
        Use AI to select the best draft.

        Args:
            drafts: List of draft dictionaries
            topic: The topic being written about
            profile_analysis: Profile analysis for style reference

        Returns:
            Content of the best draft
        """
        # Build comparison prompt
        drafts_text = ""
        for draft in drafts:
            drafts_text += f"\n\n=== ENTWURF {draft['draft_num']} ({draft['approach']}) ===\n"
            drafts_text += draft["content"]
            drafts_text += "\n=== ENDE ENTWURF ==="

        # Extract key style elements for comparison
        writing_style = profile_analysis.get("writing_style", {})
        linguistic = profile_analysis.get("linguistic_fingerprint", {})
        phrase_library = profile_analysis.get("phrase_library", {})

        selector_prompt = f"""Du bist ein erfahrener LinkedIn-Content-Editor. Wähle den BESTEN Entwurf aus.

**THEMA DES POSTS:**
{topic.get('title', 'Unbekannt')}

**STIL-ANFORDERUNGEN:**
- Tonalität: {writing_style.get('tone', 'Professionell')}
- Energie-Level: {linguistic.get('energy_level', 7)}/10
- Ansprache: {writing_style.get('form_of_address', 'Du')}
- Typische Hook-Phrasen: {', '.join(phrase_library.get('hook_phrases', [])[:3])}

**DIE ENTWÜRFE:**
{drafts_text}

**BEWERTUNGSKRITERIEN:**
1. **Hook-Qualität (30%):** Wie aufmerksamkeitsstark ist der erste Satz?
2. **Stil-Match (25%):** Wie gut passt der Entwurf zum beschriebenen Stil?
3. **Mehrwert (25%):** Wie viel konkreten Nutzen bietet der Post?
4. **Natürlichkeit (20%):** Wie authentisch und menschlich klingt er?

**AUFGABE:**
Analysiere jeden Entwurf kurz und wähle den besten. Antworte im JSON-Format:

{{
  "analysis": [
    {{"draft": 1, "hook_score": 8, "style_score": 7, "value_score": 8, "natural_score": 7, "total": 30, "notes": "Kurze Begründung"}},
    ...
  ],
  "winner": 1,
  "reason": "Kurze Begründung für die Wahl"
}}"""

        response = await self.call_openai(
            system_prompt="Du bist ein Content-Editor, der LinkedIn-Posts bewertet und den besten auswählt.",
            user_prompt=selector_prompt,
            model="gpt-4o-mini",  # Use cheaper model for selection
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        try:
            result = json.loads(response)
            winner_num = result.get("winner", 1)
            reason = result.get("reason", "")

            # Find the winning draft
            winning_draft = next(
                (d for d in drafts if d["draft_num"] == winner_num),
                drafts[0]  # Fallback to first draft
            )

            logger.info(f"Selected draft {winner_num} ({winning_draft['approach']}): {reason}")
            return winning_draft["content"]

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse selector response, using first draft: {e}")
            return drafts[0]["content"]

    async def _write_single_draft(
        self,
        topic: Dict[str, Any],
        profile_analysis: Dict[str, Any],
        feedback: Optional[str] = None,
        previous_version: Optional[str] = None,
        example_posts: Optional[List[str]] = None,
        critic_result: Optional[Dict[str, Any]] = None,
        learned_lessons: Optional[Dict[str, Any]] = None
    ) -> str:
        """Write a single draft (original behavior)."""
        # Select examples if not already selected
        if example_posts is None:
            example_posts = []

        selected_examples = example_posts
        if not feedback and not previous_version:
            # Only select for initial posts, not revisions
            if len(selected_examples) == 0:
                pass  # No examples available
            elif len(selected_examples) > 3:
                selected_examples = random.sample(selected_examples, 3)

        system_prompt = self._get_system_prompt(profile_analysis, selected_examples, learned_lessons)
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

    def _get_system_prompt(
        self,
        profile_analysis: Dict[str, Any],
        example_posts: List[str] = None,
        learned_lessons: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get system prompt for writer - orientiert an bewährten n8n-Prompts."""
        # Extract key profile information
        writing_style = profile_analysis.get("writing_style", {})
        linguistic = profile_analysis.get("linguistic_fingerprint", {})
        tone_analysis = profile_analysis.get("tone_analysis", {})
        visual = profile_analysis.get("visual_patterns", {})
        content_strategy = profile_analysis.get("content_strategy", {})
        audience = profile_analysis.get("audience_insights", {})
        phrase_library = profile_analysis.get("phrase_library", {})
        structure_templates = profile_analysis.get("structure_templates", {})

        # Build example posts section
        examples_section = ""
        if example_posts and len(example_posts) > 0:
            examples_section = "\n\nREFERENZ-POSTS DER PERSON (Orientiere dich am Stil!):\n"
            for i, post in enumerate(example_posts, 1):
                post_text = post[:1800] + "..." if len(post) > 1800 else post
                examples_section += f"\n--- Beispiel {i} ---\n{post_text}\n"
            examples_section += "--- Ende Beispiele ---\n"

        # Safe extraction of nested values
        emoji_list = visual.get('emoji_usage', {}).get('emojis', ['🚀'])
        emoji_str = ' '.join(emoji_list) if isinstance(emoji_list, list) else str(emoji_list)
        sig_phrases = linguistic.get('signature_phrases', [])
        narrative_anchors = linguistic.get('narrative_anchors', [])
        narrative_str = ', '.join(narrative_anchors) if narrative_anchors else 'Storytelling'
        pain_points = audience.get('pain_points_addressed', [])
        pain_points_str = ', '.join(pain_points) if pain_points else 'Branchenspezifische Herausforderungen'

        # Extract phrase library with variation instruction
        hook_phrases = phrase_library.get('hook_phrases', [])
        transition_phrases = phrase_library.get('transition_phrases', [])
        emotional_expressions = phrase_library.get('emotional_expressions', [])
        cta_phrases = phrase_library.get('cta_phrases', [])
        filler_expressions = phrase_library.get('filler_expressions', [])

        # Randomly select a subset of phrases for this post (variation!)
        def select_phrases(phrases: list, max_count: int = 3) -> str:
            if not phrases:
                return "Keine verfügbar"
            selected = random.sample(phrases, min(max_count, len(phrases)))
            return '\n  - '.join(selected)

        # Extract structure templates
        primary_structure = structure_templates.get('primary_structure', 'Hook → Body → CTA')
        sentence_starters = structure_templates.get('typical_sentence_starters', [])
        paragraph_transitions = structure_templates.get('paragraph_transitions', [])

        # Build phrase library section
        phrase_section = ""
        if hook_phrases or emotional_expressions or cta_phrases:
            phrase_section = f"""

2. PHRASEN-BIBLIOTHEK (Wähle passende aus - NICHT alle verwenden!):

HOOK-VORLAGEN (lass dich inspirieren, kopiere nicht 1:1):
  - {select_phrases(hook_phrases, 4)}

ÜBERGANGS-PHRASEN (nutze 1-2 davon):
  - {select_phrases(transition_phrases, 3)}

EMOTIONALE AUSDRÜCKE (nutze 1-2 passende):
  - {select_phrases(emotional_expressions, 4)}

CTA-FORMULIERUNGEN (wähle eine passende):
  - {select_phrases(cta_phrases, 3)}

FÜLL-AUSDRÜCKE (für natürlichen Flow):
  - {select_phrases(filler_expressions, 3)}

SIGNATURE PHRASES (nutze maximal 1-2 ORGANISCH):
  - {select_phrases(sig_phrases, 4)}

WICHTIG: Variiere! Nutze NICHT immer die gleichen Phrasen. Wähle die, die zum Thema passen.
"""

        # Build structure section
        structure_section = f"""

3. STRUKTUR-TEMPLATE:

Primäre Struktur: {primary_structure}

Typische Satzanfänge (nutze ähnliche):
  - {select_phrases(sentence_starters, 4)}

Absatz-Übergänge:
  - {select_phrases(paragraph_transitions, 3)}
"""

        # Build lessons learned section (from past feedback)
        lessons_section = ""
        if learned_lessons and learned_lessons.get("lessons"):
            lessons_section = "\n\n6. LESSONS LEARNED (aus vergangenen Posts - BEACHTE DIESE!):\n"
            patterns = learned_lessons.get("patterns", {})
            if patterns.get("posts_analyzed", 0) > 0:
                lessons_section += f"\n(Basierend auf {patterns.get('posts_analyzed', 0)} analysierten Posts, Durchschnittsscore: {patterns.get('avg_score', 0):.0f}/100)\n"

            for lesson in learned_lessons["lessons"]:
                if lesson["type"] == "critical":
                    lessons_section += f"\n⚠️ KRITISCH - {lesson['message']}\n"
                    for item in lesson["items"]:
                        lessons_section += f"  ❌ {item}\n"
                elif lesson["type"] == "recurring":
                    lessons_section += f"\n📝 {lesson['message']}\n"
                    for item in lesson["items"]:
                        lessons_section += f"  • {item}\n"

            lessons_section += "\nBerücksichtige diese Punkte PROAKTIV beim Schreiben!"

        return f"""ROLLE: Du bist ein erstklassiger Ghostwriter für LinkedIn. Deine Aufgabe ist es, einen Post zu schreiben, der exakt so klingt wie der digitale Zwilling der beschriebenen Person. Du passt dich zu 100% an das bereitgestellte Profil an.
{examples_section}

1. STIL & ENERGIE:

Energie-Level (1-10): {linguistic.get('energy_level', 7)}
(WICHTIG: Passe die Intensität und Leidenschaft des Textes EXAKT an diesen Wert an. Bei 9-10 = hochemotional, bei 5-6 = sachlich-professionell)

Rhetorisches Shouting: {linguistic.get('shouting_usage', 'Dezent')}
(Nutze GROSSBUCHSTABEN für einzelne Wörter genau so wie hier beschrieben, um Emphase zu erzeugen - mach das für KEINE anderen Wörter!)

Tonalität: {tone_analysis.get('primary_tone', 'Professionell und authentisch')}

Ansprache (STRENGSTENS EINHALTEN): {writing_style.get('form_of_address', 'Du/Euch')}

Perspektive (STRENGSTENS EINHALTEN): {writing_style.get('perspective', 'Ich-Perspektive')}

Satz-Dynamik: {writing_style.get('sentence_dynamics', 'Mix aus kurzen und längeren Sätzen')}
Interpunktion: {linguistic.get('punctuation_patterns', 'Standard')}

Branche: {audience.get('industry_context', 'Business')}

Zielgruppe: {audience.get('target_audience', 'Professionals')}
{phrase_section}
{structure_section}

4. VISUELLE REGELN:

Unicode-Fettung: Nutze für den ersten Satz (Hook) fette Unicode-Zeichen (z.B. 𝗪𝗶𝗰𝗵𝘁𝗶𝗴𝗲𝗿 𝗦𝗮𝘁𝘇), sofern das zur Person passt: {visual.get('unicode_formatting', 'Fett für Hooks')}

Emoji-Logik: Verwende diese Emojis: {emoji_str}
Platzierung: {visual.get('emoji_usage', {}).get('placement', 'Ende')}
Häufigkeit: {visual.get('emoji_usage', {}).get('frequency', 'Mittel')}

Erzähl-Anker: Baue Elemente ein wie: {narrative_str}
(Falls 'PS-Zeilen', 'Dialoge' oder 'Flashbacks' genannt sind, integriere diese wenn es passt.)

Layout: {visual.get('structure_preferences', 'Kurze Absätze, mobil-optimiert')}

Länge: Ca. {writing_style.get('average_word_count', 300)} Wörter

CTA: Beende den Post mit einer Variante von: {content_strategy.get('cta_style', 'Interaktive Frage an die Community')}


5. GUARDRAILS (VERBOTE!):

Vermeide IMMER diese KI-typischen Muster:
- "In der heutigen Zeit", "Tauchen Sie ein", "Es ist kein Geheimnis"
- "Stellen Sie sich vor", "Lassen Sie uns", "Es ist wichtig zu verstehen"
- Gedankenstriche (–) zur Satzverbindung - nutze stattdessen Kommas oder Punkte
- Belehrende Formulierungen wenn die Person eine Ich-Perspektive nutzt
- Übertriebene Superlative ohne Substanz
- Zu perfekte, glatte Formulierungen - echte Menschen schreiben mit Ecken und Kanten
{lessons_section}

DEIN AUFTRAG: Schreibe den Post so, dass er für die Zielgruppe ({audience.get('target_audience', 'Professionals')}) einen klaren Mehrwert bietet und ihre Pain Points ({pain_points_str}) adressiert. Mach die Persönlichkeit des linguistischen Fingerabdrucks spürbar.

Beginne DIREKT mit dem Hook. Keine einleitenden Sätze, kein "Hier ist der Post"."""

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
            # Initial writing mode - enhanced with new topic fields
            angle_section = ""
            if topic.get('angle'):
                angle_section = f"\n**ANGLE/PERSPEKTIVE:**\n{topic.get('angle')}\n"

            hook_section = ""
            if topic.get('hook_idea'):
                hook_section = f"\n**HOOK-IDEE (als Inspiration):**\n\"{topic.get('hook_idea')}\"\n"

            facts_section = ""
            key_facts = topic.get('key_facts', [])
            if key_facts and isinstance(key_facts, list) and len(key_facts) > 0:
                facts_section = "\n**KEY FACTS (nutze diese!):**\n" + "\n".join([f"- {f}" for f in key_facts]) + "\n"

            return f"""Schreibe einen LinkedIn-Post zu folgendem Thema:

**THEMA:** {topic.get('title', 'Unbekanntes Thema')}

**KATEGORIE:** {topic.get('category', 'Allgemein')}
{angle_section}{hook_section}
**KERN-FAKT / INHALT:**
{topic.get('fact', topic.get('description', ''))}
{facts_section}
**WARUM RELEVANT:**
{topic.get('relevance', 'Aktuelles Thema für die Zielgruppe')}

**AUFGABE:**
Schreibe einen authentischen LinkedIn-Post, der:
1. Mit einem STARKEN, unerwarteten Hook beginnt (nutze Hook-Idee als Inspiration!)
2. Den Fakt/das Thema aufgreift und Mehrwert bietet
3. Die Key Facts einbaut wo es passt
4. Eine persönliche Note oder Meinung enthält
5. Mit einem passenden CTA endet

WICHTIG:
- Vermeide KI-typische Formulierungen ("In der heutigen Zeit", "Tauchen Sie ein", etc.)
- Schreibe natürlich und menschlich
- Der Post soll SOFORT 85+ Punkte im Review erreichen

Gib NUR den fertigen Post zurück."""
