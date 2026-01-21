"""Topic extractor agent."""
import json
from typing import List, Dict, Any
from loguru import logger

from src.agents.base import BaseAgent
from src.database.models import LinkedInPost, Topic


class TopicExtractorAgent(BaseAgent):
    """Agent for extracting topics from LinkedIn posts."""

    def __init__(self):
        """Initialize topic extractor agent."""
        super().__init__("TopicExtractor")

    async def process(self, posts: List[LinkedInPost], customer_id) -> List[Topic]:
        """
        Extract topics from LinkedIn posts.

        Args:
            posts: List of LinkedIn posts
            customer_id: Customer UUID (as UUID or string)

        Returns:
            List of extracted topics
        """
        logger.info(f"Extracting topics from {len(posts)} posts")

        # Prepare posts for analysis
        posts_data = []
        for idx, post in enumerate(posts[:30]):  # Analyze up to 30 posts
            posts_data.append({
                "index": idx,
                "post_id": str(post.id) if post.id else None,
                "text": post.post_text[:500],  # Limit text length
                "date": str(post.post_date) if post.post_date else None
            })

        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(posts_data)

        response = await self.call_openai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="gpt-4o",
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # Parse response
        result = json.loads(response)
        topics_data = result.get("topics", [])

        # Create Topic objects
        topics = []
        for topic_data in topics_data:
            # Get post index from topic_data if available
            post_index = topic_data.get("post_id")
            extracted_from_post_id = None

            # Map post index to actual post ID
            if post_index is not None and isinstance(post_index, (int, str)):
                try:
                    # Convert to int if it's a string representation
                    idx = int(post_index) if isinstance(post_index, str) else post_index
                    # Get the actual post from the posts list
                    if 0 <= idx < len(posts) and posts[idx].id:
                        extracted_from_post_id = posts[idx].id
                except (ValueError, IndexError):
                    logger.warning(f"Could not map post index {post_index} to post ID")

            topic = Topic(
                customer_id=customer_id,  # Will be handled by Pydantic
                title=topic_data["title"],
                description=topic_data.get("description"),
                category=topic_data.get("category"),
                extracted_from_post_id=extracted_from_post_id,
                extraction_confidence=topic_data.get("confidence", 0.8)
            )
            topics.append(topic)

        logger.info(f"Extracted {len(topics)} topics")
        return topics

    def _get_system_prompt(self) -> str:
        """Get system prompt for topic extraction."""
        return """Du bist ein AI-Experte für Themenanalyse und Content-Kategorisierung.

Deine Aufgabe ist es, aus einer Liste von LinkedIn-Posts die Hauptthemen zu extrahieren.

Für jedes identifizierte Thema sollst du:
1. Ein prägnantes Titel geben
2. Eine kurze Beschreibung verfassen
3. Eine Kategorie zuweisen (z.B. "Technologie", "Strategie", "Personal Development", etc.)
4. Die Konfidenz angeben (0.0 - 1.0)

Wichtig:
- Fasse ähnliche Themen zusammen (z.B. "KI im Marketing" und "AI-Tools" → "KI & Automatisierung")
- Identifiziere übergeordnete Themen-Cluster
- Sei präzise und konkret
- Vermeide zu allgemeine Themen wie "Business" oder "Erfolg"

Gib deine Antwort als JSON zurück."""

    def _get_user_prompt(self, posts_data: List[Dict[str, Any]]) -> str:
        """Get user prompt with posts data."""
        posts_text = json.dumps(posts_data, indent=2, ensure_ascii=False)

        return f"""Analysiere folgende LinkedIn-Posts und extrahiere die Hauptthemen:

{posts_text}

Gib deine Analyse im folgenden JSON-Format zurück:

{{
  "topics": [
    {{
      "title": "Thementitel",
      "description": "Kurze Beschreibung des Themas",
      "category": "Kategorie",
      "post_id": "ID des repräsentativen Posts (optional)",
      "confidence": 0.9,
      "frequency": "Wie oft kommt das Thema vor?"
    }}
  ]
}}

Extrahiere 5-10 Hauptthemen."""
