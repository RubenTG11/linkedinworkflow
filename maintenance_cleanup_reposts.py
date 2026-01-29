#!/usr/bin/env python3
"""
Maintenance script to remove repost/non-regular posts from the database.

This removes LinkedIn posts that are reposts, shares, or any other non-original content.
Only posts with post_type "regular" in their raw_data should remain.

Usage:
    python maintenance_cleanup_reposts.py          # Dry run (preview what will be deleted)
    python maintenance_cleanup_reposts.py --apply  # Actually delete the posts
"""

import asyncio
import sys
from uuid import UUID

from loguru import logger

from src.database import db


async def cleanup_reposts(apply: bool = False):
    """
    Find and remove all non-regular posts from the database.

    Args:
        apply: If True, delete posts. If False, just preview.
    """
    logger.info("Loading all customers...")
    customers = await db.list_customers()

    total_posts = 0
    regular_posts = 0
    posts_to_delete = []

    for customer in customers:
        posts = await db.get_linkedin_posts(customer.id)

        for post in posts:
            total_posts += 1

            # Check post_type in raw_data
            post_type = None
            if post.raw_data and isinstance(post.raw_data, dict):
                post_type = post.raw_data.get("post_type", "").lower()

            if post_type == "regular":
                regular_posts += 1
            else:
                posts_to_delete.append({
                    'id': post.id,
                    'customer': customer.name,
                    'post_type': post_type or 'unknown',
                    'text_preview': (post.post_text[:80] + '...') if post.post_text and len(post.post_text) > 80 else post.post_text,
                    'url': post.post_url
                })

    # Print summary
    print(f"\n{'='*70}")
    print(f"SCAN RESULTS")
    print(f"{'='*70}")
    print(f"Total posts scanned:     {total_posts}")
    print(f"Regular posts (keep):    {regular_posts}")
    print(f"Non-regular (delete):    {len(posts_to_delete)}")

    if not posts_to_delete:
        print("\nNo posts to delete! Database is clean.")
        return

    # Show posts to delete
    print(f"\n{'='*70}")
    print(f"POSTS TO DELETE")
    print(f"{'='*70}")

    # Group by post_type for cleaner output
    by_type = {}
    for post in posts_to_delete:
        pt = post['post_type']
        if pt not in by_type:
            by_type[pt] = []
        by_type[pt].append(post)

    for post_type, posts in by_type.items():
        print(f"\n[{post_type.upper()}] - {len(posts)} posts")
        print("-" * 50)
        for post in posts[:5]:  # Show max 5 per type
            print(f"  Customer: {post['customer']}")
            print(f"  Preview:  {post['text_preview']}")
            print(f"  ID:       {post['id']}")
            print()
        if len(posts) > 5:
            print(f"  ... and {len(posts) - 5} more {post_type} posts\n")

    if apply:
        print(f"\n{'='*70}")
        print(f"DELETING {len(posts_to_delete)} POSTS...")
        print(f"{'='*70}")

        deleted = 0
        errors = 0

        for post_data in posts_to_delete:
            try:
                await asyncio.to_thread(
                    lambda pid=post_data['id']:
                        db.client.table("linkedin_posts").delete().eq("id", str(pid)).execute()
                )
                deleted += 1
                if deleted % 10 == 0:
                    print(f"  Deleted {deleted}/{len(posts_to_delete)}...")
            except Exception as e:
                logger.error(f"Failed to delete post {post_data['id']}: {e}")
                errors += 1

        print(f"\nDone! Deleted {deleted} posts. Errors: {errors}")
    else:
        print(f"\n{'='*70}")
        print(f"DRY RUN - No changes made.")
        print(f"Run with --apply to delete these {len(posts_to_delete)} posts.")
        print(f"{'='*70}")


async def main():
    apply = '--apply' in sys.argv

    if apply:
        print("="*70)
        print("MODE: DELETE POSTS")
        print("="*70)
        print(f"\nThis will permanently delete non-regular posts from the database.")
        print("This action cannot be undone!\n")
        response = input("Are you sure? Type 'DELETE' to confirm: ")
        if response != 'DELETE':
            print("Aborted.")
            return
    else:
        print("="*70)
        print("MODE: DRY RUN (preview only)")
        print("="*70)
        print("Add --apply flag to actually delete posts.\n")

    await cleanup_reposts(apply=apply)


if __name__ == "__main__":
    asyncio.run(main())
