"""Post classifier agent for categorizing LinkedIn posts into post types."""
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from loguru import logger

from src.agents.base import BaseAgent
from src.database.models import LinkedInPost, PostType


class PostClassifierAgent(BaseAgent):
    """Agent for classifying LinkedIn posts into defined post types."""

    def __init__(self):
        """Initialize post classifier agent."""
        super().__init__("PostClassifier")

    async def process(
        self,
        posts: List[LinkedInPost],
        post_types: List[PostType]
    ) -> List[Dict[str, Any]]:
        """
        Classify posts into post types.

        Uses a two-phase approach:
        1. Hashtag matching (fast, deterministic)
        2. Semantic matching via LLM (for posts without hashtag match)

        Args:
            posts: List of posts to classify
            post_types: List of available post types

        Returns:
            List of classification results with post_id, post_type_id, method, confidence
        """
        if not posts or not post_types:
            logger.warning("No posts or post types to classify")
            return []

        logger.info(f"Classifying {len(posts)} posts into {len(post_types)} post types")

        classifications = []
        posts_needing_semantic = []

        # Phase 1: Hashtag matching
        for post in posts:
            result = self._match_by_hashtags(post, post_types)
            if result:
                classifications.append(result)
            else:
                posts_needing_semantic.append(post)

        logger.info(f"Hashtag matching: {len(classifications)} matched, {len(posts_needing_semantic)} need semantic")

        # Phase 2: Semantic matching for remaining posts
        if posts_needing_semantic:
            semantic_results = await self._match_semantically(posts_needing_semantic, post_types)
            classifications.extend(semantic_results)

        logger.info(f"Classification complete: {len(classifications)} total classifications")
        return classifications

    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from post text (lowercase for matching)."""
        hashtags = re.findall(r'#(\w+)', text)
        return [h.lower() for h in hashtags]

    def _match_by_hashtags(
        self,
        post: LinkedInPost,
        post_types: List[PostType]
    ) -> Optional[Dict[str, Any]]:
        """
        Try to match post to a post type by hashtags.

        Args:
            post: The post to classify
            post_types: Available post types

        Returns:
            Classification dict or None if no match
        """
        post_hashtags = set(self._extract_hashtags(post.post_text))

        if not post_hashtags:
            return None

        best_match = None
        best_match_count = 0

        for pt in post_types:
            if not pt.identifying_hashtags:
                continue

            # Convert post type hashtags to lowercase for comparison
            pt_hashtags = set(h.lower().lstrip('#') for h in pt.identifying_hashtags)

            # Count matching hashtags
            matches = post_hashtags.intersection(pt_hashtags)

            if matches and len(matches) > best_match_count:
                best_match = pt
                best_match_count = len(matches)

        if best_match:
            # Confidence based on how many hashtags matched
            confidence = min(1.0, best_match_count * 0.25 + 0.5)
            return {
                "post_id": post.id,
                "post_type_id": best_match.id,
                "classification_method": "hashtag",
                "classification_confidence": confidence
            }

        return None

    async def _match_semantically(
        self,
        posts: List[LinkedInPost],
        post_types: List[PostType]
    ) -> List[Dict[str, Any]]:
        """
        Match posts to post types using semantic analysis via LLM.

        Args:
            posts: Posts to classify
            post_types: Available post types

        Returns:
            List of classification results
        """
        if not posts:
            return []

        # Build post type descriptions for the LLM
        type_descriptions = []
        for pt in post_types:
            desc = f"- **{pt.name}** (ID: {pt.id})"
            if pt.description:
                desc += f": {pt.description}"
            if pt.identifying_keywords:
                desc += f"\n  Keywords: {', '.join(pt.identifying_keywords[:10])}"
            if pt.semantic_properties:
                props = pt.semantic_properties
                if props.get("purpose"):
                    desc += f"\n  Purpose: {props['purpose']}"
                if props.get("typical_tone"):
                    desc += f"\n  Tone: {props['typical_tone']}"
            type_descriptions.append(desc)

        type_descriptions_text = "\n".join(type_descriptions)

        # Process in batches for efficiency
        batch_size = 10
        results = []

        for i in range(0, len(posts), batch_size):
            batch = posts[i:i + batch_size]
            batch_results = await self._classify_batch(batch, post_types, type_descriptions_text)
            results.extend(batch_results)

        return results

    async def _classify_batch(
        self,
        posts: List[LinkedInPost],
        post_types: List[PostType],
        type_descriptions: str
    ) -> List[Dict[str, Any]]:
        """Classify a batch of posts using LLM."""
        # Build post list for prompt
        posts_list = []
        for i, post in enumerate(posts):
            post_preview = post.post_text[:500] + "..." if len(post.post_text) > 500 else post.post_text
            posts_list.append(f"[Post {i + 1}] (ID: {post.id})\n{post_preview}")

        posts_text = "\n\n".join(posts_list)

        # Build valid type IDs for validation
        valid_type_ids = {str(pt.id) for pt in post_types}
        valid_type_ids.add("null")  # Allow unclassified

        system_prompt = """Du bist ein Content-Analyst, der LinkedIn-Posts in vordefinierte Kategorien einordnet.

Analysiere jeden Post und ordne ihn dem passendsten Post-Typ zu.
Wenn kein Typ wirklich passt, gib "null" als post_type_id zurück.

Bewerte die Zuordnung mit einer Confidence zwischen 0.3 und 1.0:
- 0.9-1.0: Sehr sicher, Post passt perfekt zum Typ
- 0.7-0.9: Gute Übereinstimmung
- 0.5-0.7: Moderate Übereinstimmung
- 0.3-0.5: Schwache Übereinstimmung, aber beste verfügbare Option

Antworte im JSON-Format."""

        user_prompt = f"""Ordne die folgenden Posts den verfügbaren Post-Typen zu:

=== VERFÜGBARE POST-TYPEN ===
{type_descriptions}

=== POSTS ZUM KLASSIFIZIEREN ===
{posts_text}

=== ANTWORT-FORMAT ===
Gib ein JSON-Objekt zurück mit diesem Format:
{{
  "classifications": [
    {{
      "post_id": "uuid-des-posts",
      "post_type_id": "uuid-des-typs oder null",
      "confidence": 0.8,
      "reasoning": "Kurze Begründung"
    }}
  ]
}}"""

        try:
            response = await self.call_openai(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model="gpt-4o-mini",
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            result = json.loads(response)
            classifications = result.get("classifications", [])

            # Process and validate results
            valid_results = []
            for c in classifications:
                post_id = c.get("post_id")
                post_type_id = c.get("post_type_id")
                confidence = c.get("confidence", 0.5)

                # Validate post_id exists
                matching_post = next((p for p in posts if str(p.id) == post_id), None)
                if not matching_post:
                    logger.warning(f"Invalid post_id in classification: {post_id}")
                    continue

                # Validate post_type_id
                if post_type_id and post_type_id != "null" and post_type_id not in valid_type_ids:
                    logger.warning(f"Invalid post_type_id in classification: {post_type_id}")
                    continue

                if post_type_id and post_type_id != "null":
                    valid_results.append({
                        "post_id": matching_post.id,
                        "post_type_id": UUID(post_type_id),
                        "classification_method": "semantic",
                        "classification_confidence": min(1.0, max(0.3, confidence))
                    })

            return valid_results

        except Exception as e:
            logger.error(f"Semantic classification failed: {e}")
            return []

    async def classify_single_post(
        self,
        post: LinkedInPost,
        post_types: List[PostType]
    ) -> Optional[Dict[str, Any]]:
        """
        Classify a single post.

        Args:
            post: The post to classify
            post_types: Available post types

        Returns:
            Classification result or None
        """
        results = await self.process([post], post_types)
        return results[0] if results else None
