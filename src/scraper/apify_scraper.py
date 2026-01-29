"""LinkedIn posts scraper using Apify (apimaestro~linkedin-profile-posts)."""
import asyncio
from typing import Dict, Any, List
from apify_client import ApifyClient
from loguru import logger

from src.config import settings


class LinkedInScraper:
    """LinkedIn posts scraper using Apify."""

    def __init__(self):
        """Initialize Apify client."""
        self.client = ApifyClient(settings.apify_api_key)
        logger.info("Apify client initialized")

    async def scrape_posts(self, linkedin_url: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape posts from a LinkedIn profile.

        Args:
            linkedin_url: URL of the LinkedIn profile
            limit: Maximum number of posts to scrape

        Returns:
            List of post dictionaries
        """
        logger.info(f"Scraping posts from: {linkedin_url}")

        # Extract username from LinkedIn URL
        # Example: https://www.linkedin.com/in/christinahildebrandt/ -> christinahildebrandt
        username = self._extract_username_from_url(linkedin_url)
        logger.info(f"Extracted username: {username}")

        # Prepare the Actor input for apimaestro~linkedin-profile-posts
        run_input = {
            "username": username,
            "page_number": 1,
            "limit": limit,
        }

        try:
            # Run the Actor in thread pool to avoid blocking event loop
            run = await asyncio.to_thread(
                self.client.actor(settings.apify_actor_id).call,
                run_input=run_input
            )

            # Fetch results from the run's dataset in thread pool
            dataset_items = await asyncio.to_thread(
                lambda: list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            )


            if not dataset_items:
                logger.warning("No posts found")
                return []

            logger.info(f"Successfully scraped {len(dataset_items)} posts")
            return dataset_items

        except Exception as e:
            logger.error(f"Error scraping posts: {e}")
            raise

    def _extract_username_from_url(self, linkedin_url: str) -> str:
        """
        Extract username from LinkedIn URL.

        Args:
            linkedin_url: LinkedIn profile URL

        Returns:
            Username
        """
        import re

        # Remove trailing slash
        url = linkedin_url.rstrip('/')

        # Extract username from different LinkedIn URL formats
        # https://www.linkedin.com/in/username/
        # https://linkedin.com/in/username
        # www.linkedin.com/in/username
        match = re.search(r'/in/([^/]+)', url)
        if match:
            return match.group(1)

        # If no match, raise error
        raise ValueError(f"Could not extract username from LinkedIn URL: {linkedin_url}")

    def parse_posts_data(self, raw_posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse and structure the raw Apify posts data.

        Only includes posts with post_type "regular" (excludes reposts, shared posts, etc.)

        Args:
            raw_posts: List of raw post data from Apify

        Returns:
            List of structured post dictionaries
        """
        from datetime import datetime
        parsed_posts = []
        skipped_count = 0

        for post in raw_posts:
            # Only include regular posts (not reposts, shares, etc.)
            post_type = post.get("post_type", "").lower()
            if post_type != "regular":
                skipped_count += 1
                logger.debug(f"Skipping non-regular post (type: {post_type})")
                continue
            # Extract posted_at date
            posted_at_data = post.get("posted_at", {})
            post_date = None

            if isinstance(posted_at_data, dict):
                date_str = posted_at_data.get("date")
                if date_str:
                    try:
                        # Try to parse the date string
                        # Format: "2026-01-20 07:45:33"
                        post_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        # If parsing fails, keep as string
                        post_date = date_str

            # Extract stats
            stats = post.get("stats", {})

            # Create a clean copy of raw_data without datetime objects
            raw_data_clean = {}
            for key, value in post.items():
                if isinstance(value, datetime):
                    raw_data_clean[key] = value.isoformat()
                elif isinstance(value, dict):
                    # Handle nested dicts
                    raw_data_clean[key] = {}
                    for k, v in value.items():
                        if isinstance(v, datetime):
                            raw_data_clean[key][k] = v.isoformat()
                        else:
                            raw_data_clean[key][k] = v
                else:
                    raw_data_clean[key] = value

            parsed_post = {
                "post_url": post.get("url"),
                "post_text": post.get("text", ""),
                "post_date": post_date,
                "likes": stats.get("like", 0) if stats else 0,
                "comments": stats.get("comments", 0) if stats else 0,
                "shares": stats.get("reposts", 0) if stats else 0,
                "raw_data": raw_data_clean
            }
            parsed_posts.append(parsed_post)

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} non-regular posts (reposts, shares, etc.)")

        return parsed_posts


# Global scraper instance
scraper = LinkedInScraper()
