#!/usr/bin/env python3
"""
Maintenance script to convert Markdown bold (**text**) to Unicode bold.

This fixes posts that contain Markdown formatting which doesn't render on LinkedIn.
Unicode bold characters are used instead, which display correctly on LinkedIn.

Usage:
    python maintenance_fix_markdown_bold.py          # Dry run (preview changes)
    python maintenance_fix_markdown_bold.py --apply  # Apply changes to database
"""

import asyncio
import re
import sys
from uuid import UUID

from loguru import logger

from src.database import db


# Unicode Bold character mappings (Mathematical Sans-Serif Bold)
BOLD_MAP = {
    # Uppercase A-Z
    'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚',
    'H': '𝗛', 'I': '𝗜', 'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡',
    'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥', 'S': '𝗦', 'T': '𝗧', 'U': '𝗨',
    'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭',
    # Lowercase a-z
    'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴',
    'h': '𝗵', 'i': '𝗶', 'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻',
    'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿', 's': '𝘀', 't': '𝘁', 'u': '𝘂',
    'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
    # Numbers 0-9
    '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰',
    '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵',
    # German umlauts
    'Ä': '𝗔̈', 'Ö': '𝗢̈', 'Ü': '𝗨̈',
    'ä': '𝗮̈', 'ö': '𝗼̈', 'ü': '𝘂̈',
    'ß': 'ß',  # No bold variant, keep as is
}


def to_unicode_bold(text: str) -> str:
    """Convert plain text to Unicode bold characters."""
    result = []
    for char in text:
        result.append(BOLD_MAP.get(char, char))
    return ''.join(result)


def convert_markdown_bold(content: str) -> str:
    """
    Convert Markdown bold (**text**) to Unicode bold.

    Also handles:
    - __text__ (alternative markdown bold)
    - Nested or multiple occurrences
    """
    # Pattern for **text** (non-greedy, handles multiple)
    pattern_asterisk = r'\*\*(.+?)\*\*'
    # Pattern for __text__
    pattern_underscore = r'__(.+?)__'

    def replace_with_bold(match):
        inner_text = match.group(1)
        return to_unicode_bold(inner_text)

    # Apply conversions
    result = re.sub(pattern_asterisk, replace_with_bold, content)
    result = re.sub(pattern_underscore, replace_with_bold, result)

    return result


def has_markdown_bold(content: str) -> bool:
    """Check if content contains Markdown bold syntax."""
    return bool(re.search(r'\*\*.+?\*\*|__.+?__', content))


async def fix_all_posts(apply: bool = False):
    """
    Find and fix all posts with Markdown bold formatting.

    Args:
        apply: If True, apply changes to database. If False, just preview.
    """
    logger.info("Loading all customers...")
    customers = await db.list_customers()

    total_posts = 0
    posts_with_markdown = 0
    fixed_posts = []

    for customer in customers:
        posts = await db.get_generated_posts(customer.id)

        for post in posts:
            total_posts += 1

            if not post.post_content:
                continue

            if has_markdown_bold(post.post_content):
                posts_with_markdown += 1
                original = post.post_content
                converted = convert_markdown_bold(original)

                fixed_posts.append({
                    'id': post.id,
                    'customer': customer.name,
                    'topic': post.topic_title,
                    'original': original,
                    'converted': converted,
                })

                # Show preview
                print(f"\n{'='*60}")
                print(f"Post: {post.topic_title}")
                print(f"Customer: {customer.name}")
                print(f"ID: {post.id}")
                print(f"{'-'*60}")

                # Find and highlight the changes
                bold_matches = re.findall(r'\*\*(.+?)\*\*|__(.+?)__', original)
                for match in bold_matches:
                    text = match[0] or match[1]
                    print(f"  **{text}** → {to_unicode_bold(text)}")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total posts scanned: {total_posts}")
    print(f"Posts with Markdown bold: {posts_with_markdown}")

    if not fixed_posts:
        print("\nNo posts need fixing!")
        return

    if apply:
        print(f"\nApplying changes to {len(fixed_posts)} posts...")

        for post_data in fixed_posts:
            try:
                # Update the post in database
                await asyncio.to_thread(
                    lambda pid=post_data['id'], content=post_data['converted']:
                        db.client.table("generated_posts").update({
                            "post_content": content
                        }).eq("id", str(pid)).execute()
                )
                logger.info(f"Fixed post: {post_data['topic']}")
            except Exception as e:
                logger.error(f"Failed to update post {post_data['id']}: {e}")

        print(f"\nDone! Fixed {len(fixed_posts)} posts.")
    else:
        print(f"\nDRY RUN - No changes applied.")
        print(f"Run with --apply to fix these {len(fixed_posts)} posts.")


async def main():
    apply = '--apply' in sys.argv

    if apply:
        print("MODE: APPLY CHANGES")
        print("This will modify posts in the database.")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("MODE: DRY RUN (preview only)")
        print("Add --apply flag to actually modify posts.\n")

    await fix_all_posts(apply=apply)


if __name__ == "__main__":
    asyncio.run(main())
