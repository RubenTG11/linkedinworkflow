#!/usr/bin/env python3
"""
Maintenance script to extract and save topics for existing customers.

This script:
1. Loads all customers
2. For each customer, extracts topics from existing posts
3. Saves extracted topics to the topics table
4. Also saves any topics from research results to the topics table
"""
import asyncio
from loguru import logger

from src.database import db
from src.agents import TopicExtractorAgent


async def extract_and_save_topics_for_customer(customer_id):
    """Extract and save topics for a single customer."""
    logger.info(f"Processing customer: {customer_id}")

    # Get customer
    customer = await db.get_customer(customer_id)
    if not customer:
        logger.error(f"Customer {customer_id} not found")
        return

    logger.info(f"Customer: {customer.name}")

    # Get LinkedIn posts
    posts = await db.get_linkedin_posts(customer_id)
    logger.info(f"Found {len(posts)} posts")

    if not posts:
        logger.warning("No posts found, skipping topic extraction")
    else:
        # Extract topics from posts
        logger.info("Extracting topics from posts...")
        topic_extractor = TopicExtractorAgent()

        try:
            topics = await topic_extractor.process(
                posts=posts,
                customer_id=customer_id
            )

            if topics:
                # Save topics
                saved_topics = await db.save_topics(topics)
                logger.info(f"✓ Saved {len(saved_topics)} extracted topics")
            else:
                logger.warning("No topics extracted")

        except Exception as e:
            logger.error(f"Failed to extract topics: {e}", exc_info=True)

    logger.info(f"Finished processing customer: {customer.name}\n")


async def main():
    """Main function."""
    logger.info("=== TOPIC EXTRACTION MAINTENANCE SCRIPT ===\n")

    # List all customers
    customers = await db.list_customers()

    if not customers:
        logger.warning("No customers found")
        return

    logger.info(f"Found {len(customers)} customers\n")

    # Process each customer
    for customer in customers:
        try:
            await extract_and_save_topics_for_customer(customer.id)
        except Exception as e:
            logger.error(f"Error processing customer {customer.id}: {e}", exc_info=True)

    logger.info("\n=== MAINTENANCE COMPLETE ===")


if __name__ == "__main__":
    # Setup logging
    logger.add(
        "logs/maintenance_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )

    # Run
    asyncio.run(main())
