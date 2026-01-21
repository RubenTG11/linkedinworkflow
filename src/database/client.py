"""Supabase database client."""
import asyncio
from typing import Optional, List, Dict, Any
from uuid import UUID
from supabase import create_client, Client
from loguru import logger

from src.config import settings
from src.database.models import (
    Customer, LinkedInProfile, LinkedInPost, Topic,
    ProfileAnalysis, ResearchResult, GeneratedPost
)


class DatabaseClient:
    """Supabase database client wrapper."""

    def __init__(self):
        """Initialize Supabase client."""
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        logger.info("Supabase client initialized")

    # ==================== CUSTOMERS ====================

    async def create_customer(self, customer: Customer) -> Customer:
        """Create a new customer."""
        data = customer.model_dump(exclude={"id", "created_at", "updated_at"}, exclude_none=True)
        result = await asyncio.to_thread(
            lambda: self.client.table("customers").insert(data).execute()
        )
        logger.info(f"Created customer: {result.data[0]['id']}")
        return Customer(**result.data[0])

    async def get_customer(self, customer_id: UUID) -> Optional[Customer]:
        """Get customer by ID."""
        result = await asyncio.to_thread(
            lambda: self.client.table("customers").select("*").eq("id", str(customer_id)).execute()
        )
        if result.data:
            return Customer(**result.data[0])
        return None

    async def get_customer_by_linkedin(self, linkedin_url: str) -> Optional[Customer]:
        """Get customer by LinkedIn URL."""
        result = await asyncio.to_thread(
            lambda: self.client.table("customers").select("*").eq("linkedin_url", linkedin_url).execute()
        )
        if result.data:
            return Customer(**result.data[0])
        return None

    async def list_customers(self) -> List[Customer]:
        """List all customers."""
        result = await asyncio.to_thread(
            lambda: self.client.table("customers").select("*").execute()
        )
        return [Customer(**item) for item in result.data]

    # ==================== LINKEDIN PROFILES ====================

    async def save_linkedin_profile(self, profile: LinkedInProfile) -> LinkedInProfile:
        """Save or update LinkedIn profile."""
        data = profile.model_dump(exclude={"id", "scraped_at"}, exclude_none=True)
        # Convert UUID to string for Supabase
        if "customer_id" in data:
            data["customer_id"] = str(data["customer_id"])

        # Check if profile exists
        existing = await asyncio.to_thread(
            lambda: self.client.table("linkedin_profiles").select("*").eq(
                "customer_id", str(profile.customer_id)
            ).execute()
        )

        if existing.data:
            # Update existing
            result = await asyncio.to_thread(
                lambda: self.client.table("linkedin_profiles").update(data).eq(
                    "customer_id", str(profile.customer_id)
                ).execute()
            )
        else:
            # Insert new
            result = await asyncio.to_thread(
                lambda: self.client.table("linkedin_profiles").insert(data).execute()
            )

        logger.info(f"Saved LinkedIn profile for customer: {profile.customer_id}")
        return LinkedInProfile(**result.data[0])

    async def get_linkedin_profile(self, customer_id: UUID) -> Optional[LinkedInProfile]:
        """Get LinkedIn profile for customer."""
        result = await asyncio.to_thread(
            lambda: self.client.table("linkedin_profiles").select("*").eq(
                "customer_id", str(customer_id)
            ).execute()
        )
        if result.data:
            return LinkedInProfile(**result.data[0])
        return None

    # ==================== LINKEDIN POSTS ====================

    async def save_linkedin_posts(self, posts: List[LinkedInPost]) -> List[LinkedInPost]:
        """Save LinkedIn posts (bulk)."""
        from datetime import datetime

        # Deduplicate posts based on (customer_id, post_url) before saving
        seen = set()
        unique_posts = []
        for p in posts:
            key = (str(p.customer_id), p.post_url)
            if key not in seen:
                seen.add(key)
                unique_posts.append(p)

        if len(posts) != len(unique_posts):
            logger.warning(f"Removed {len(posts) - len(unique_posts)} duplicate posts from batch")

        data = []
        for p in unique_posts:
            post_dict = p.model_dump(exclude={"id", "scraped_at"}, exclude_none=True)
            # Convert UUID to string for Supabase
            if "customer_id" in post_dict:
                post_dict["customer_id"] = str(post_dict["customer_id"])

            # Convert datetime to ISO string for Supabase
            if "post_date" in post_dict and isinstance(post_dict["post_date"], datetime):
                post_dict["post_date"] = post_dict["post_date"].isoformat()

            data.append(post_dict)

        if not data:
            logger.warning("No posts to save")
            return []

        # Use upsert with on_conflict to handle duplicates based on (customer_id, post_url)
        # This will update existing posts instead of throwing an error
        result = await asyncio.to_thread(
            lambda: self.client.table("linkedin_posts").upsert(
                data,
                on_conflict="customer_id,post_url"
            ).execute()
        )
        logger.info(f"Saved {len(result.data)} LinkedIn posts")
        return [LinkedInPost(**item) for item in result.data]

    async def get_linkedin_posts(self, customer_id: UUID) -> List[LinkedInPost]:
        """Get all LinkedIn posts for customer."""
        result = await asyncio.to_thread(
            lambda: self.client.table("linkedin_posts").select("*").eq(
                "customer_id", str(customer_id)
            ).order("post_date", desc=True).execute()
        )
        return [LinkedInPost(**item) for item in result.data]

    # ==================== TOPICS ====================

    async def save_topics(self, topics: List[Topic]) -> List[Topic]:
        """Save extracted topics."""
        if not topics:
            logger.warning("No topics to save")
            return []

        data = []
        for t in topics:
            topic_dict = t.model_dump(exclude={"id", "created_at"}, exclude_none=True)
            # Convert UUID to string for Supabase
            if "customer_id" in topic_dict:
                topic_dict["customer_id"] = str(topic_dict["customer_id"])
            if "extracted_from_post_id" in topic_dict and topic_dict["extracted_from_post_id"]:
                topic_dict["extracted_from_post_id"] = str(topic_dict["extracted_from_post_id"])
            data.append(topic_dict)

        try:
            # Use insert and handle duplicates manually
            result = await asyncio.to_thread(
                lambda: self.client.table("topics").insert(data).execute()
            )
            logger.info(f"Saved {len(result.data)} topics to database")
            return [Topic(**item) for item in result.data]
        except Exception as e:
            logger.error(f"Error saving topics: {e}", exc_info=True)
            # Try one by one if batch fails
            saved = []
            for topic_data in data:
                try:
                    result = await asyncio.to_thread(
                        lambda td=topic_data: self.client.table("topics").insert(td).execute()
                    )
                    saved.extend([Topic(**item) for item in result.data])
                except Exception as single_error:
                    logger.warning(f"Skipped duplicate topic: {topic_data.get('title')}")
            logger.info(f"Saved {len(saved)} topics individually")
            return saved

    async def get_topics(self, customer_id: UUID, unused_only: bool = False) -> List[Topic]:
        """Get topics for customer."""
        def _query():
            query = self.client.table("topics").select("*").eq("customer_id", str(customer_id))
            if unused_only:
                query = query.eq("is_used", False)
            return query.order("created_at", desc=True).execute()

        result = await asyncio.to_thread(_query)
        return [Topic(**item) for item in result.data]

    async def mark_topic_used(self, topic_id: UUID) -> None:
        """Mark topic as used."""
        await asyncio.to_thread(
            lambda: self.client.table("topics").update({
                "is_used": True,
                "used_at": "now()"
            }).eq("id", str(topic_id)).execute()
        )
        logger.info(f"Marked topic {topic_id} as used")

    # ==================== PROFILE ANALYSIS ====================

    async def save_profile_analysis(self, analysis: ProfileAnalysis) -> ProfileAnalysis:
        """Save profile analysis."""
        data = analysis.model_dump(exclude={"id", "created_at"}, exclude_none=True)
        # Convert UUID to string for Supabase
        if "customer_id" in data:
            data["customer_id"] = str(data["customer_id"])

        # Check if analysis exists
        existing = await asyncio.to_thread(
            lambda: self.client.table("profile_analyses").select("*").eq(
                "customer_id", str(analysis.customer_id)
            ).execute()
        )

        if existing.data:
            # Update existing
            result = await asyncio.to_thread(
                lambda: self.client.table("profile_analyses").update(data).eq(
                    "customer_id", str(analysis.customer_id)
                ).execute()
            )
        else:
            # Insert new
            result = await asyncio.to_thread(
                lambda: self.client.table("profile_analyses").insert(data).execute()
            )

        logger.info(f"Saved profile analysis for customer: {analysis.customer_id}")
        return ProfileAnalysis(**result.data[0])

    async def get_profile_analysis(self, customer_id: UUID) -> Optional[ProfileAnalysis]:
        """Get profile analysis for customer."""
        result = await asyncio.to_thread(
            lambda: self.client.table("profile_analyses").select("*").eq(
                "customer_id", str(customer_id)
            ).execute()
        )
        if result.data:
            return ProfileAnalysis(**result.data[0])
        return None

    # ==================== RESEARCH RESULTS ====================

    async def save_research_result(self, research: ResearchResult) -> ResearchResult:
        """Save research result."""
        data = research.model_dump(exclude={"id", "created_at"}, exclude_none=True)
        # Convert UUID to string for Supabase
        if "customer_id" in data:
            data["customer_id"] = str(data["customer_id"])

        result = await asyncio.to_thread(
            lambda: self.client.table("research_results").insert(data).execute()
        )
        logger.info(f"Saved research result for customer: {research.customer_id}")
        return ResearchResult(**result.data[0])

    async def get_latest_research(self, customer_id: UUID) -> Optional[ResearchResult]:
        """Get latest research result for customer."""
        result = await asyncio.to_thread(
            lambda: self.client.table("research_results").select("*").eq(
                "customer_id", str(customer_id)
            ).order("created_at", desc=True).limit(1).execute()
        )
        if result.data:
            return ResearchResult(**result.data[0])
        return None

    async def get_all_research(self, customer_id: UUID) -> List[ResearchResult]:
        """Get all research results for customer."""
        result = await asyncio.to_thread(
            lambda: self.client.table("research_results").select("*").eq(
                "customer_id", str(customer_id)
            ).order("created_at", desc=True).execute()
        )
        return [ResearchResult(**item) for item in result.data]

    # ==================== GENERATED POSTS ====================

    async def save_generated_post(self, post: GeneratedPost) -> GeneratedPost:
        """Save generated post."""
        data = post.model_dump(exclude={"id", "created_at"}, exclude_none=True)
        # Convert UUIDs to string for Supabase
        if "customer_id" in data:
            data["customer_id"] = str(data["customer_id"])
        if "topic_id" in data and data["topic_id"]:
            data["topic_id"] = str(data["topic_id"])

        result = await asyncio.to_thread(
            lambda: self.client.table("generated_posts").insert(data).execute()
        )
        logger.info(f"Saved generated post: {result.data[0]['id']}")
        return GeneratedPost(**result.data[0])

    async def update_generated_post(self, post_id: UUID, updates: Dict[str, Any]) -> GeneratedPost:
        """Update generated post."""
        result = await asyncio.to_thread(
            lambda: self.client.table("generated_posts").update(updates).eq(
                "id", str(post_id)
            ).execute()
        )
        logger.info(f"Updated generated post: {post_id}")
        return GeneratedPost(**result.data[0])

    async def get_generated_posts(self, customer_id: UUID) -> List[GeneratedPost]:
        """Get all generated posts for customer."""
        result = await asyncio.to_thread(
            lambda: self.client.table("generated_posts").select("*").eq(
                "customer_id", str(customer_id)
            ).order("created_at", desc=True).execute()
        )
        return [GeneratedPost(**item) for item in result.data]


# Global database client instance
db = DatabaseClient()
