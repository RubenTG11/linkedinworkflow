"""Main orchestrator for the LinkedIn workflow."""
from collections import Counter
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID
from loguru import logger

from src.config import settings
from src.database import db, Customer, LinkedInProfile, LinkedInPost, Topic
from src.scraper import scraper
from src.agents import (
    ProfileAnalyzerAgent,
    TopicExtractorAgent,
    ResearchAgent,
    WriterAgent,
    CriticAgent,
    PostClassifierAgent,
    PostTypeAnalyzerAgent,
)
from src.database.models import PostType


class WorkflowOrchestrator:
    """Orchestrates the entire LinkedIn post creation workflow."""

    def __init__(self):
        """Initialize orchestrator with all agents."""
        self.profile_analyzer = ProfileAnalyzerAgent()
        self.topic_extractor = TopicExtractorAgent()
        self.researcher = ResearchAgent()
        self.writer = WriterAgent()
        self.critic = CriticAgent()
        self.post_classifier = PostClassifierAgent()
        self.post_type_analyzer = PostTypeAnalyzerAgent()
        logger.info("WorkflowOrchestrator initialized")

    async def run_initial_setup(
        self,
        linkedin_url: str,
        customer_name: str,
        customer_data: Dict[str, Any],
        post_types_data: Optional[List[Dict[str, Any]]] = None
    ) -> Customer:
        """
        Run initial setup for a new customer.

        This includes:
        1. Creating customer record
        2. Creating post types (if provided)
        3. Scraping LinkedIn posts (NO profile scraping)
        4. Creating profile from customer_data
        5. Analyzing profile
        6. Extracting topics from existing posts
        7. Classifying posts by type (if post types exist)
        8. Analyzing post types (if enough posts)

        Args:
            linkedin_url: LinkedIn profile URL
            customer_name: Customer name
            customer_data: Complete customer data (company, persona, style_guide, etc.)
            post_types_data: Optional list of post type definitions

        Returns:
            Customer object
        """
        logger.info(f"=== INITIAL SETUP for {customer_name} ===")

        # Step 1: Check if customer already exists
        existing_customer = await db.get_customer_by_linkedin(linkedin_url)
        if existing_customer:
            logger.warning(f"Customer already exists: {existing_customer.id}")
            return existing_customer

        # Step 2: Create customer
        total_steps = 7 if post_types_data else 5
        logger.info(f"Step 1/{total_steps}: Creating customer record")
        customer = Customer(
            name=customer_name,
            linkedin_url=linkedin_url,
            company_name=customer_data.get("company_name"),
            email=customer_data.get("email"),
            metadata=customer_data
        )
        customer = await db.create_customer(customer)
        logger.info(f"Customer created: {customer.id}")

        # Step 2.5: Create post types if provided
        created_post_types = []
        if post_types_data:
            logger.info(f"Step 2/{total_steps}: Creating {len(post_types_data)} post types")
            for pt_data in post_types_data:
                post_type = PostType(
                    customer_id=customer.id,
                    name=pt_data.get("name", "Unnamed"),
                    description=pt_data.get("description"),
                    identifying_hashtags=pt_data.get("identifying_hashtags", []),
                    identifying_keywords=pt_data.get("identifying_keywords", []),
                    semantic_properties=pt_data.get("semantic_properties", {})
                )
                created_post_types.append(post_type)

            if created_post_types:
                created_post_types = await db.create_post_types_bulk(created_post_types)
                logger.info(f"Created {len(created_post_types)} post types")

        # Step 3: Create LinkedIn profile from customer data (NO scraping)
        step_num = 3 if post_types_data else 2
        logger.info(f"Step {step_num}/{total_steps}: Creating LinkedIn profile from provided data")
        linkedin_profile = LinkedInProfile(
            customer_id=customer.id,
            profile_data={
                "persona": customer_data.get("persona"),
                "form_of_address": customer_data.get("form_of_address"),
                "style_guide": customer_data.get("style_guide"),
                "linkedin_url": linkedin_url
            },
            name=customer_name,
            headline=customer_data.get("persona", "")[:100] if customer_data.get("persona") else None
        )
        await db.save_linkedin_profile(linkedin_profile)
        logger.info("LinkedIn profile saved")

        # Step 4: Scrape ONLY posts using Apify
        step_num = 4 if post_types_data else 3
        logger.info(f"Step {step_num}/{total_steps}: Scraping LinkedIn posts")
        try:
            raw_posts = await scraper.scrape_posts(linkedin_url, limit=50)
            parsed_posts = scraper.parse_posts_data(raw_posts)

            linkedin_posts = []
            for post_data in parsed_posts:
                post = LinkedInPost(
                    customer_id=customer.id,
                    **post_data
                )
                linkedin_posts.append(post)

            if linkedin_posts:
                await db.save_linkedin_posts(linkedin_posts)
                logger.info(f"Saved {len(linkedin_posts)} posts")
            else:
                logger.warning("No posts scraped")
                linkedin_posts = []
        except Exception as e:
            logger.error(f"Failed to scrape posts: {e}")
            linkedin_posts = []

        # Step 5: Analyze profile (with manual data + scraped posts)
        step_num = 5 if post_types_data else 4
        logger.info(f"Step {step_num}/{total_steps}: Analyzing profile with AI")
        try:
            profile_analysis = await self.profile_analyzer.process(
                profile=linkedin_profile,
                posts=linkedin_posts,
                customer_data=customer_data
            )

            # Save profile analysis
            from src.database.models import ProfileAnalysis
            analysis_record = ProfileAnalysis(
                customer_id=customer.id,
                writing_style=profile_analysis.get("writing_style", {}),
                tone_analysis=profile_analysis.get("tone_analysis", {}),
                topic_patterns=profile_analysis.get("topic_patterns", {}),
                audience_insights=profile_analysis.get("audience_insights", {}),
                full_analysis=profile_analysis
            )
            await db.save_profile_analysis(analysis_record)
            logger.info("Profile analysis saved")
        except Exception as e:
            logger.error(f"Profile analysis failed: {e}", exc_info=True)
            raise

        # Step 6: Extract topics from posts
        step_num = 6 if post_types_data else 5
        logger.info(f"Step {step_num}/{total_steps}: Extracting topics from posts")
        if linkedin_posts:
            try:
                topics = await self.topic_extractor.process(
                    posts=linkedin_posts,
                    customer_id=customer.id  # Pass UUID directly
                )
                if topics:
                    await db.save_topics(topics)
                    logger.info(f"Extracted and saved {len(topics)} topics")
            except Exception as e:
                logger.error(f"Topic extraction failed: {e}", exc_info=True)
        else:
            logger.info("No posts to extract topics from")

        # Step 7 & 8: Classify and analyze post types (if post types exist)
        if created_post_types and linkedin_posts:
            # Step 7: Classify posts
            logger.info(f"Step {total_steps - 1}/{total_steps}: Classifying posts by type")
            try:
                await self.classify_posts(customer.id)
            except Exception as e:
                logger.error(f"Post classification failed: {e}", exc_info=True)

            # Step 8: Analyze post types
            logger.info(f"Step {total_steps}/{total_steps}: Analyzing post types")
            try:
                await self.analyze_post_types(customer.id)
            except Exception as e:
                logger.error(f"Post type analysis failed: {e}", exc_info=True)

        logger.info(f"Step {total_steps}/{total_steps}: Initial setup complete!")
        return customer

    async def classify_posts(self, customer_id: UUID) -> int:
        """
        Classify unclassified posts for a customer.

        Args:
            customer_id: Customer UUID

        Returns:
            Number of posts classified
        """
        logger.info(f"=== CLASSIFYING POSTS for customer {customer_id} ===")

        # Get post types
        post_types = await db.get_post_types(customer_id)
        if not post_types:
            logger.info("No post types defined, skipping classification")
            return 0

        # Get unclassified posts
        posts = await db.get_unclassified_posts(customer_id)
        if not posts:
            logger.info("No unclassified posts found")
            return 0

        logger.info(f"Classifying {len(posts)} posts into {len(post_types)} types")

        # Run classification
        classifications = await self.post_classifier.process(posts, post_types)

        if classifications:
            # Bulk update classifications
            await db.update_posts_classification_bulk(classifications)
            logger.info(f"Classified {len(classifications)} posts")
            return len(classifications)

        return 0

    async def analyze_post_types(self, customer_id: UUID) -> Dict[str, Any]:
        """
        Analyze all post types for a customer.

        Args:
            customer_id: Customer UUID

        Returns:
            Dictionary with analysis results per post type
        """
        logger.info(f"=== ANALYZING POST TYPES for customer {customer_id} ===")

        # Get post types
        post_types = await db.get_post_types(customer_id)
        if not post_types:
            logger.info("No post types defined")
            return {}

        results = {}
        for post_type in post_types:
            # Get posts for this type
            posts = await db.get_posts_by_type(customer_id, post_type.id)

            if len(posts) < self.post_type_analyzer.MIN_POSTS_FOR_ANALYSIS:
                logger.info(f"Post type '{post_type.name}' has only {len(posts)} posts, skipping analysis")
                results[str(post_type.id)] = {
                    "skipped": True,
                    "reason": f"Not enough posts ({len(posts)} < {self.post_type_analyzer.MIN_POSTS_FOR_ANALYSIS})"
                }
                continue

            # Run analysis
            logger.info(f"Analyzing post type '{post_type.name}' with {len(posts)} posts")
            analysis = await self.post_type_analyzer.process(post_type, posts)

            # Save analysis to database
            if analysis.get("sufficient_data"):
                await db.update_post_type_analysis(
                    post_type_id=post_type.id,
                    analysis=analysis,
                    analyzed_post_count=len(posts)
                )

            results[str(post_type.id)] = analysis

        return results

    async def research_new_topics(
        self,
        customer_id: UUID,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        post_type_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Research new content topics for a customer.

        Args:
            customer_id: Customer UUID
            progress_callback: Optional callback(message, current_step, total_steps)
            post_type_id: Optional post type to target research for

        Returns:
            List of suggested topics
        """
        logger.info(f"=== RESEARCHING NEW TOPICS for customer {customer_id} ===")

        # Get post type context if specified
        post_type = None
        post_type_analysis = None
        if post_type_id:
            post_type = await db.get_post_type(post_type_id)
            if post_type:
                post_type_analysis = post_type.analysis
                logger.info(f"Targeting research for post type: {post_type.name}")

        def report_progress(message: str, step: int, total: int = 4):
            if progress_callback:
                progress_callback(message, step, total)

        # Step 1: Get profile analysis
        report_progress("Lade Profil-Analyse...", 1)
        profile_analysis = await db.get_profile_analysis(customer_id)
        if not profile_analysis:
            raise ValueError("Profile analysis not found. Run initial setup first.")

        # Step 2: Get ALL existing topics (from multiple sources to avoid repetition)
        report_progress("Lade existierende Topics...", 2)
        existing_topics = set()

        # From topics table
        existing_topics_records = await db.get_topics(customer_id)
        for t in existing_topics_records:
            existing_topics.add(t.title)

        # From previous research results
        all_research = await db.get_all_research(customer_id)
        for research in all_research:
            if research.suggested_topics:
                for topic in research.suggested_topics:
                    if topic.get("title"):
                        existing_topics.add(topic["title"])

        # From generated posts
        generated_posts = await db.get_generated_posts(customer_id)
        for post in generated_posts:
            if post.topic_title:
                existing_topics.add(post.topic_title)

        existing_topics = list(existing_topics)
        logger.info(f"Found {len(existing_topics)} existing topics to avoid")

        # Get customer data
        customer = await db.get_customer(customer_id)

        # Get example posts to understand the person's actual content style
        # If post_type_id is specified, only use posts of that type
        if post_type_id:
            linkedin_posts = await db.get_posts_by_type(customer_id, post_type_id)
        else:
            linkedin_posts = await db.get_linkedin_posts(customer_id)

        example_post_texts = [
            post.post_text for post in linkedin_posts
            if post.post_text and len(post.post_text) > 100  # Only substantial posts
        ][:15]  # Limit to 15 best examples
        logger.info(f"Loaded {len(example_post_texts)} example posts for research context")

        # Step 3: Run research
        report_progress("AI recherchiert neue Topics...", 3)
        logger.info("Running research with AI")
        research_results = await self.researcher.process(
            profile_analysis=profile_analysis.full_analysis,
            existing_topics=existing_topics,
            customer_data=customer.metadata,
            example_posts=example_post_texts,
            post_type=post_type,
            post_type_analysis=post_type_analysis
        )

        # Step 4: Save research results
        report_progress("Speichere Ergebnisse...", 4)
        from src.database.models import ResearchResult
        research_record = ResearchResult(
            customer_id=customer_id,
            query=f"New topics for {customer.name}" + (f" ({post_type.name})" if post_type else ""),
            results={"raw_response": research_results["raw_response"]},
            suggested_topics=research_results["suggested_topics"],
            target_post_type_id=post_type_id
        )
        await db.save_research_result(research_record)
        logger.info(f"Research completed with {len(research_results['suggested_topics'])} suggestions")

        return research_results["suggested_topics"]

    async def create_post(
        self,
        customer_id: UUID,
        topic: Dict[str, Any],
        max_iterations: int = 3,
        progress_callback: Optional[Callable[[str, int, int, Optional[int], Optional[List], Optional[List]], None]] = None,
        post_type_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Create a LinkedIn post through writer-critic iteration.

        Args:
            customer_id: Customer UUID
            topic: Topic dictionary
            max_iterations: Maximum number of writer-critic iterations
            progress_callback: Optional callback(message, iteration, max_iterations, score, versions, feedback_list)
            post_type_id: Optional post type for type-specific writing

        Returns:
            Dictionary with final post and metadata
        """
        logger.info(f"=== CREATING POST for topic: {topic.get('title')} ===")

        def report_progress(message: str, iteration: int, score: Optional[int] = None,
                          versions: Optional[List] = None, feedback_list: Optional[List] = None):
            if progress_callback:
                progress_callback(message, iteration, max_iterations, score, versions, feedback_list)

        # Get profile analysis
        report_progress("Lade Profil-Analyse...", 0, None, [], [])
        profile_analysis = await db.get_profile_analysis(customer_id)
        if not profile_analysis:
            raise ValueError("Profile analysis not found. Run initial setup first.")

        # Get post type info if specified
        post_type = None
        post_type_analysis = None
        if post_type_id:
            post_type = await db.get_post_type(post_type_id)
            if post_type and post_type.analysis:
                post_type_analysis = post_type.analysis
                logger.info(f"Using post type '{post_type.name}' for writing")

        # Load customer's real posts as style examples
        # If post_type_id is specified, only use posts of that type
        if post_type_id:
            linkedin_posts = await db.get_posts_by_type(customer_id, post_type_id)
            if len(linkedin_posts) < 3:
                # Fall back to all posts if not enough type-specific posts
                linkedin_posts = await db.get_linkedin_posts(customer_id)
                logger.info("Not enough type-specific posts, using all posts")
        else:
            linkedin_posts = await db.get_linkedin_posts(customer_id)

        example_post_texts = [
            post.post_text for post in linkedin_posts
            if post.post_text and len(post.post_text) > 100  # Only use substantial posts
        ]
        logger.info(f"Loaded {len(example_post_texts)} example posts for style reference")

        # Extract lessons from past feedback (if enabled)
        feedback_lessons = await self._extract_recurring_feedback(customer_id)

        # Initialize tracking
        writer_versions = []
        critic_feedback_list = []
        current_post = None
        approved = False
        iteration = 0

        # Writer-Critic loop
        while iteration < max_iterations and not approved:
            iteration += 1
            logger.info(f"--- Iteration {iteration}/{max_iterations} ---")

            # Writer creates/revises post
            if iteration == 1:
                # Initial post
                report_progress("Writer erstellt ersten Entwurf...", iteration, None, writer_versions, critic_feedback_list)
                current_post = await self.writer.process(
                    topic=topic,
                    profile_analysis=profile_analysis.full_analysis,
                    example_posts=example_post_texts,
                    learned_lessons=feedback_lessons,  # Pass lessons from past feedback
                    post_type=post_type,
                    post_type_analysis=post_type_analysis
                )
            else:
                # Revision based on feedback - pass full critic result for structured changes
                report_progress("Writer überarbeitet Post...", iteration, None, writer_versions, critic_feedback_list)
                last_feedback = critic_feedback_list[-1]
                current_post = await self.writer.process(
                    topic=topic,
                    profile_analysis=profile_analysis.full_analysis,
                    feedback=last_feedback.get("feedback", ""),
                    previous_version=writer_versions[-1],
                    example_posts=example_post_texts,
                    critic_result=last_feedback,  # Pass full critic result with specific_changes
                    learned_lessons=feedback_lessons,  # Also for revisions
                    post_type=post_type,
                    post_type_analysis=post_type_analysis
                )

            writer_versions.append(current_post)
            logger.info(f"Writer produced version {iteration}")

            # Report progress with new version
            report_progress("Critic bewertet Post...", iteration, None, writer_versions, critic_feedback_list)

            # Critic reviews post with iteration awareness
            critic_result = await self.critic.process(
                post=current_post,
                profile_analysis=profile_analysis.full_analysis,
                topic=topic,
                example_posts=example_post_texts,
                iteration=iteration,
                max_iterations=max_iterations
            )
            critic_feedback_list.append(critic_result)

            approved = critic_result.get("approved", False)
            score = critic_result.get("overall_score", 0)

            # Auto-approve on last iteration if score is decent (>= 80)
            if iteration == max_iterations and not approved and score >= 80:
                approved = True
                critic_result["approved"] = True
                logger.info(f"Auto-approved on final iteration with score {score}")

            logger.info(f"Critic score: {score}/100 | Approved: {approved}")

            if approved:
                report_progress("Post genehmigt!", iteration, score, writer_versions, critic_feedback_list)
                logger.info("Post approved!")
                break
            else:
                report_progress(f"Score: {score}/100 - Überarbeitung nötig", iteration, score, writer_versions, critic_feedback_list)

            if iteration < max_iterations:
                logger.info("Post needs revision, continuing...")

        # Determine final status based on score
        final_score = critic_feedback_list[-1].get("overall_score", 0) if critic_feedback_list else 0
        if approved and final_score >= 85:
            status = "approved"
        elif approved and final_score >= 80:
            status = "approved"  # Auto-approved
        else:
            status = "draft"

        # Save generated post
        from src.database.models import GeneratedPost
        generated_post = GeneratedPost(
            customer_id=customer_id,
            topic_title=topic.get("title", "Unknown"),
            post_content=current_post,
            iterations=iteration,
            writer_versions=writer_versions,
            critic_feedback=critic_feedback_list,
            status=status,
            post_type_id=post_type_id
        )
        saved_post = await db.save_generated_post(generated_post)

        logger.info(f"Post creation complete after {iteration} iterations")

        return {
            "post_id": saved_post.id,
            "final_post": current_post,
            "iterations": iteration,
            "approved": approved,
            "final_score": critic_feedback_list[-1].get("overall_score", 0) if critic_feedback_list else 0,
            "writer_versions": writer_versions,
            "critic_feedback": critic_feedback_list
        }

    async def _extract_recurring_feedback(self, customer_id: UUID) -> Dict[str, Any]:
        """
        Extract recurring feedback patterns from past generated posts.

        Args:
            customer_id: Customer UUID

        Returns:
            Dictionary with recurring improvements and lessons learned
        """
        if not settings.writer_learn_from_feedback:
            return {"lessons": [], "patterns": {}}

        # Get recent generated posts with their critic feedback
        generated_posts = await db.get_generated_posts(customer_id)

        if not generated_posts:
            return {"lessons": [], "patterns": {}}

        # Limit to recent posts
        recent_posts = generated_posts[:settings.writer_feedback_history_count]

        # Collect all improvements from final feedback
        all_improvements = []
        all_scores = []
        low_score_issues = []  # Issues from posts that scored < 85

        for post in recent_posts:
            if not post.critic_feedback:
                continue

            # Get final feedback (last in list)
            final_feedback = post.critic_feedback[-1] if post.critic_feedback else None
            if not final_feedback:
                continue

            score = final_feedback.get("overall_score", 0)
            all_scores.append(score)

            # Collect improvements
            improvements = final_feedback.get("improvements", [])
            all_improvements.extend(improvements)

            # Track issues from lower-scoring posts
            if score < 85:
                low_score_issues.extend(improvements)

        if not all_improvements:
            return {"lessons": [], "patterns": {}}

        # Count frequency of improvements (normalized)
        def normalize_improvement(text: str) -> str:
            """Normalize improvement text for comparison."""
            text = text.lower().strip()
            # Remove common prefixes
            for prefix in ["der ", "die ", "das ", "mehr ", "weniger ", "zu "]:
                if text.startswith(prefix):
                    text = text[len(prefix):]
            return text[:50]  # Limit length for comparison

        improvement_counts = Counter([normalize_improvement(imp) for imp in all_improvements])
        low_score_counts = Counter([normalize_improvement(imp) for imp in low_score_issues])

        # Find recurring issues (mentioned 2+ times)
        recurring_issues = [
            imp for imp, count in improvement_counts.most_common(10)
            if count >= 2
        ]

        # Find critical issues (from low-scoring posts, mentioned 2+ times)
        critical_issues = [
            imp for imp, count in low_score_counts.most_common(5)
            if count >= 2
        ]

        # Build lessons learned
        lessons = []

        if critical_issues:
            lessons.append({
                "type": "critical",
                "message": "Diese Punkte führten zu niedrigen Scores - UNBEDINGT vermeiden:",
                "items": critical_issues[:3]
            })

        if recurring_issues:
            # Filter out critical issues
            non_critical = [r for r in recurring_issues if r not in critical_issues]
            if non_critical:
                lessons.append({
                    "type": "recurring",
                    "message": "Häufig genannte Verbesserungspunkte aus vergangenen Posts:",
                    "items": non_critical[:4]
                })

        # Calculate average score for context
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

        logger.info(f"Extracted feedback from {len(recent_posts)} posts: {len(lessons)} lesson categories, avg score: {avg_score:.1f}")

        return {
            "lessons": lessons,
            "patterns": {
                "avg_score": avg_score,
                "posts_analyzed": len(recent_posts),
                "recurring_count": len(recurring_issues),
                "critical_count": len(critical_issues)
            }
        }

    async def get_customer_status(self, customer_id: UUID) -> Dict[str, Any]:
        """
        Get status information for a customer.

        Args:
            customer_id: Customer UUID

        Returns:
            Status dictionary
        """
        customer = await db.get_customer(customer_id)
        if not customer:
            raise ValueError("Customer not found")

        profile = await db.get_linkedin_profile(customer_id)
        posts = await db.get_linkedin_posts(customer_id)
        analysis = await db.get_profile_analysis(customer_id)
        generated_posts = await db.get_generated_posts(customer_id)
        all_research = await db.get_all_research(customer_id)
        post_types = await db.get_post_types(customer_id)

        # Count total research entries
        research_count = len(all_research)

        # Count classified posts
        classified_posts = [p for p in posts if p.post_type_id]

        # Count analyzed post types
        analyzed_types = [pt for pt in post_types if pt.analysis]

        # Check what's missing
        missing_items = []
        if not posts:
            missing_items.append("LinkedIn Posts (Scraping)")
        if not analysis:
            missing_items.append("Profil-Analyse")
        if research_count == 0:
            missing_items.append("Research Topics")

        # Ready for posts if we have scraped posts and profile analysis
        ready_for_posts = len(posts) > 0 and analysis is not None

        return {
            "has_scraped_posts": len(posts) > 0,
            "scraped_posts_count": len(posts),
            "has_profile_analysis": analysis is not None,
            "research_count": research_count,
            "posts_count": len(generated_posts),
            "ready_for_posts": ready_for_posts,
            "missing_items": missing_items,
            "post_types_count": len(post_types),
            "classified_posts_count": len(classified_posts),
            "analyzed_types_count": len(analyzed_types)
        }


# Global orchestrator instance
orchestrator = WorkflowOrchestrator()
