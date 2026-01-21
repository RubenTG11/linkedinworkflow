"""Main orchestrator for the LinkedIn workflow."""
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID
from loguru import logger

from src.database import db, Customer, LinkedInProfile, LinkedInPost, Topic
from src.scraper import scraper
from src.agents import (
    ProfileAnalyzerAgent,
    TopicExtractorAgent,
    ResearchAgent,
    WriterAgent,
    CriticAgent,
)


class WorkflowOrchestrator:
    """Orchestrates the entire LinkedIn post creation workflow."""

    def __init__(self):
        """Initialize orchestrator with all agents."""
        self.profile_analyzer = ProfileAnalyzerAgent()
        self.topic_extractor = TopicExtractorAgent()
        self.researcher = ResearchAgent()
        self.writer = WriterAgent()
        self.critic = CriticAgent()
        logger.info("WorkflowOrchestrator initialized")

    async def run_initial_setup(
        self,
        linkedin_url: str,
        customer_name: str,
        customer_data: Dict[str, Any]
    ) -> Customer:
        """
        Run initial setup for a new customer.

        This includes:
        1. Creating customer record
        2. Scraping LinkedIn posts (NO profile scraping)
        3. Creating profile from customer_data
        4. Analyzing profile
        5. Extracting topics from existing posts
        6. Storing everything in database

        Args:
            linkedin_url: LinkedIn profile URL
            customer_name: Customer name
            customer_data: Complete customer data (company, persona, style_guide, etc.)

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
        logger.info("Step 1/5: Creating customer record")
        customer = Customer(
            name=customer_name,
            linkedin_url=linkedin_url,
            company_name=customer_data.get("company_name"),
            email=customer_data.get("email"),
            metadata=customer_data
        )
        customer = await db.create_customer(customer)
        logger.info(f"Customer created: {customer.id}")

        # Step 3: Create LinkedIn profile from customer data (NO scraping)
        logger.info("Step 2/5: Creating LinkedIn profile from provided data")
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
        logger.info("Step 3/5: Scraping LinkedIn posts")
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
        logger.info("Step 4/5: Analyzing profile with AI")
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
        logger.info("Step 5/5: Extracting topics from posts")
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

        logger.info("Step 5/5: Initial setup complete!")
        return customer

    async def research_new_topics(
        self,
        customer_id: UUID,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Research new content topics for a customer.

        Args:
            customer_id: Customer UUID
            progress_callback: Optional callback(message, current_step, total_steps)

        Returns:
            List of suggested topics
        """
        logger.info(f"=== RESEARCHING NEW TOPICS for customer {customer_id} ===")

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

        # Step 3: Run research
        report_progress("AI recherchiert neue Topics...", 3)
        logger.info("Running research with AI")
        research_results = await self.researcher.process(
            profile_analysis=profile_analysis.full_analysis,
            existing_topics=existing_topics,
            customer_data=customer.metadata
        )

        # Step 4: Save research results
        report_progress("Speichere Ergebnisse...", 4)
        from src.database.models import ResearchResult
        research_record = ResearchResult(
            customer_id=customer_id,
            query=f"New topics for {customer.name}",
            results={"raw_response": research_results["raw_response"]},
            suggested_topics=research_results["suggested_topics"]
        )
        await db.save_research_result(research_record)
        logger.info(f"Research completed with {len(research_results['suggested_topics'])} suggestions")

        return research_results["suggested_topics"]

    async def create_post(
        self,
        customer_id: UUID,
        topic: Dict[str, Any],
        max_iterations: int = 3,
        progress_callback: Optional[Callable[[str, int, int, Optional[int]], None]] = None
    ) -> Dict[str, Any]:
        """
        Create a LinkedIn post through writer-critic iteration.

        Args:
            customer_id: Customer UUID
            topic: Topic dictionary
            max_iterations: Maximum number of writer-critic iterations
            progress_callback: Optional callback(message, iteration, max_iterations, score)

        Returns:
            Dictionary with final post and metadata
        """
        logger.info(f"=== CREATING POST for topic: {topic.get('title')} ===")

        def report_progress(message: str, iteration: int, score: Optional[int] = None):
            if progress_callback:
                progress_callback(message, iteration, max_iterations, score)

        # Get profile analysis
        report_progress("Lade Profil-Analyse...", 0)
        profile_analysis = await db.get_profile_analysis(customer_id)
        if not profile_analysis:
            raise ValueError("Profile analysis not found. Run initial setup first.")

        # Load customer's real posts as style examples
        linkedin_posts = await db.get_linkedin_posts(customer_id)
        example_post_texts = [
            post.post_text for post in linkedin_posts
            if post.post_text and len(post.post_text) > 100  # Only use substantial posts
        ]
        logger.info(f"Loaded {len(example_post_texts)} example posts for style reference")

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
                report_progress("Writer erstellt ersten Entwurf...", iteration)
                current_post = await self.writer.process(
                    topic=topic,
                    profile_analysis=profile_analysis.full_analysis,
                    example_posts=example_post_texts
                )
            else:
                # Revision based on feedback - pass full critic result for structured changes
                report_progress("Writer überarbeitet Post...", iteration)
                last_feedback = critic_feedback_list[-1]
                current_post = await self.writer.process(
                    topic=topic,
                    profile_analysis=profile_analysis.full_analysis,
                    feedback=last_feedback.get("feedback", ""),
                    previous_version=writer_versions[-1],
                    example_posts=example_post_texts,
                    critic_result=last_feedback  # Pass full critic result with specific_changes
                )

            writer_versions.append(current_post)
            logger.info(f"Writer produced version {iteration}")

            # Critic reviews post with iteration awareness
            report_progress("Critic bewertet Post...", iteration)
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
                report_progress("Post genehmigt!", iteration, score)
                logger.info("Post approved!")
                break
            else:
                report_progress(f"Score: {score}/100 - Überarbeitung nötig", iteration, score)

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
            status=status
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

        # Count total research entries
        research_count = len(all_research)

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
            "missing_items": missing_items
        }


# Global orchestrator instance
orchestrator = WorkflowOrchestrator()
