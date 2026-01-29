"""User frontend routes (LinkedIn OAuth protected)."""
import asyncio
import json
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Request, Form, BackgroundTasks, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from loguru import logger

from src.config import settings
from src.database import db
from src.orchestrator import orchestrator
from src.web.user.auth import (
    get_user_session, set_user_session, clear_user_session,
    get_supabase_login_url, handle_oauth_callback, UserSession
)

# Router for user frontend
user_router = APIRouter(tags=["user"])

# Templates
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates" / "user")

# Store for progress updates
progress_store = {}


async def get_customer_profile_picture(customer_id: UUID) -> Optional[str]:
    """Get profile picture URL from customer's LinkedIn posts."""
    linkedin_posts = await db.get_linkedin_posts(customer_id)
    for lp in linkedin_posts:
        if lp.raw_data and isinstance(lp.raw_data, dict):
            author = lp.raw_data.get("author", {})
            if author and isinstance(author, dict):
                profile_picture_url = author.get("profile_picture")
                if profile_picture_url:
                    return profile_picture_url
    return None


def require_user_session(request: Request) -> Optional[UserSession]:
    """Check if user is authenticated, redirect to login if not."""
    session = get_user_session(request)
    if not session:
        return None
    return session


# ==================== AUTH ROUTES ====================

@user_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """User login page with LinkedIn OAuth button."""
    # If already logged in, redirect to dashboard
    session = get_user_session(request)
    if session:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error
    })


@user_router.get("/auth/linkedin")
async def start_oauth(request: Request):
    """Start LinkedIn OAuth flow via Supabase."""
    # Build callback URL
    callback_url = settings.supabase_redirect_url
    if not callback_url:
        # Fallback to constructing from request
        callback_url = str(request.url_for("oauth_callback"))

    login_url = get_supabase_login_url(callback_url)
    return RedirectResponse(url=login_url, status_code=302)


@user_router.get("/auth/callback")
async def oauth_callback(
    request: Request,
    access_token: str = None,
    refresh_token: str = None,
    error: str = None,
    error_description: str = None
):
    """Handle OAuth callback from Supabase."""
    if error:
        logger.error(f"OAuth error: {error} - {error_description}")
        return RedirectResponse(url=f"/login?error={error}", status_code=302)

    # Supabase returns tokens in URL hash, not query params
    # We need to handle this client-side and redirect back
    # Check if we have the tokens
    if not access_token:
        # Render a page that extracts hash params and redirects
        return templates.TemplateResponse("auth_callback.html", {
            "request": request
        })

    # We have the tokens, try to authenticate
    session = await handle_oauth_callback(access_token, refresh_token)

    if not session:
        return RedirectResponse(url="/not-authorized", status_code=302)

    # Success - set session and redirect to dashboard
    response = RedirectResponse(url="/", status_code=302)
    set_user_session(response, session)
    return response


@user_router.get("/logout")
async def logout(request: Request):
    """Log out user."""
    response = RedirectResponse(url="/login", status_code=302)
    clear_user_session(response)
    return response


@user_router.get("/not-authorized", response_class=HTMLResponse)
async def not_authorized_page(request: Request):
    """Page shown when user's LinkedIn profile doesn't match any customer."""
    return templates.TemplateResponse("not_authorized.html", {
        "request": request
    })


# ==================== PROTECTED PAGES ====================

@user_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """User dashboard - shows only their own stats."""
    session = require_user_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)

    try:
        customer_id = UUID(session.customer_id)
        customer = await db.get_customer(customer_id)
        posts = await db.get_generated_posts(customer_id)
        profile_picture = session.linkedin_picture or await get_customer_profile_picture(customer_id)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "page": "home",
            "session": session,
            "customer": customer,
            "total_posts": len(posts),
            "profile_picture": profile_picture
        })
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "page": "home",
            "session": session,
            "error": str(e)
        })


@user_router.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request):
    """View user's own posts."""
    session = require_user_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)

    try:
        customer_id = UUID(session.customer_id)
        customer = await db.get_customer(customer_id)
        posts = await db.get_generated_posts(customer_id)
        profile_picture = session.linkedin_picture or await get_customer_profile_picture(customer_id)

        return templates.TemplateResponse("posts.html", {
            "request": request,
            "page": "posts",
            "session": session,
            "customer": customer,
            "posts": posts,
            "total_posts": len(posts),
            "profile_picture": profile_picture
        })
    except Exception as e:
        logger.error(f"Error loading posts: {e}")
        return templates.TemplateResponse("posts.html", {
            "request": request,
            "page": "posts",
            "session": session,
            "posts": [],
            "total_posts": 0,
            "error": str(e)
        })


@user_router.get("/posts/{post_id}", response_class=HTMLResponse)
async def post_detail_page(request: Request, post_id: str):
    """Detailed view of a single post."""
    session = require_user_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)

    try:
        post = await db.get_generated_post(UUID(post_id))
        if not post:
            return RedirectResponse(url="/posts", status_code=302)

        # Verify user owns this post
        if str(post.customer_id) != session.customer_id:
            return RedirectResponse(url="/posts", status_code=302)

        customer = await db.get_customer(post.customer_id)
        linkedin_posts = await db.get_linkedin_posts(post.customer_id)
        reference_posts = [p.post_text for p in linkedin_posts if p.post_text and len(p.post_text) > 100][:10]

        profile_picture_url = session.linkedin_picture
        if not profile_picture_url:
            for lp in linkedin_posts:
                if lp.raw_data and isinstance(lp.raw_data, dict):
                    author = lp.raw_data.get("author", {})
                    if author and isinstance(author, dict):
                        profile_picture_url = author.get("profile_picture")
                        if profile_picture_url:
                            break

        profile_analysis_record = await db.get_profile_analysis(post.customer_id)
        profile_analysis = profile_analysis_record.full_analysis if profile_analysis_record else None

        post_type = None
        post_type_analysis = None
        if post.post_type_id:
            post_type = await db.get_post_type(post.post_type_id)
            if post_type and post_type.analysis:
                post_type_analysis = post_type.analysis

        final_feedback = None
        if post.critic_feedback and len(post.critic_feedback) > 0:
            final_feedback = post.critic_feedback[-1]

        return templates.TemplateResponse("post_detail.html", {
            "request": request,
            "page": "posts",
            "session": session,
            "post": post,
            "customer": customer,
            "reference_posts": reference_posts,
            "profile_analysis": profile_analysis,
            "post_type": post_type,
            "post_type_analysis": post_type_analysis,
            "final_feedback": final_feedback,
            "profile_picture_url": profile_picture_url
        })
    except Exception as e:
        logger.error(f"Error loading post detail: {e}")
        return RedirectResponse(url="/posts", status_code=302)


@user_router.get("/research", response_class=HTMLResponse)
async def research_page(request: Request):
    """Research topics page - no customer dropdown needed."""
    session = require_user_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("research.html", {
        "request": request,
        "page": "research",
        "session": session,
        "customer_id": session.customer_id
    })


@user_router.get("/create", response_class=HTMLResponse)
async def create_post_page(request: Request):
    """Create post page - no customer dropdown needed."""
    session = require_user_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("create_post.html", {
        "request": request,
        "page": "create",
        "session": session,
        "customer_id": session.customer_id
    })


@user_router.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """User's status page."""
    session = require_user_session(request)
    if not session:
        return RedirectResponse(url="/login", status_code=302)

    try:
        customer_id = UUID(session.customer_id)
        customer = await db.get_customer(customer_id)
        status = await orchestrator.get_customer_status(customer_id)
        profile_picture = session.linkedin_picture or await get_customer_profile_picture(customer_id)

        return templates.TemplateResponse("status.html", {
            "request": request,
            "page": "status",
            "session": session,
            "customer": customer,
            "status": status,
            "profile_picture": profile_picture
        })
    except Exception as e:
        logger.error(f"Error loading status: {e}")
        return templates.TemplateResponse("status.html", {
            "request": request,
            "page": "status",
            "session": session,
            "error": str(e)
        })


# ==================== API ENDPOINTS ====================

@user_router.get("/api/post-types")
async def get_post_types(request: Request):
    """Get post types for the logged-in user's customer."""
    session = require_user_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        post_types = await db.get_post_types(UUID(session.customer_id))
        return {
            "post_types": [
                {
                    "id": str(pt.id),
                    "name": pt.name,
                    "description": pt.description,
                    "has_analysis": pt.analysis is not None,
                    "analyzed_post_count": pt.analyzed_post_count,
                }
                for pt in post_types
            ]
        }
    except Exception as e:
        logger.error(f"Error loading post types: {e}")
        return {"post_types": [], "error": str(e)}


@user_router.get("/api/topics")
async def get_topics(request: Request, post_type_id: str = None):
    """Get research topics for the logged-in user."""
    session = require_user_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        customer_id = UUID(session.customer_id)
        if post_type_id:
            all_research = await db.get_all_research(customer_id, UUID(post_type_id))
        else:
            all_research = await db.get_all_research(customer_id)

        # Get used topics
        generated_posts = await db.get_generated_posts(customer_id)
        used_topic_titles = set()
        for post in generated_posts:
            if post.topic_title:
                used_topic_titles.add(post.topic_title.lower().strip())

        all_topics = []
        for research in all_research:
            if research.suggested_topics:
                for topic in research.suggested_topics:
                    topic_title = topic.get("title", "").lower().strip()
                    if topic_title in used_topic_titles:
                        continue
                    topic["research_id"] = str(research.id)
                    topic["target_post_type_id"] = str(research.target_post_type_id) if research.target_post_type_id else None
                    all_topics.append(topic)

        return {"topics": all_topics, "used_count": len(used_topic_titles), "available_count": len(all_topics)}
    except Exception as e:
        logger.error(f"Error loading topics: {e}")
        return {"topics": [], "error": str(e)}


@user_router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get task progress."""
    return progress_store.get(task_id, {"status": "unknown", "message": "Task not found"})


@user_router.post("/api/research")
async def start_research(request: Request, background_tasks: BackgroundTasks, post_type_id: str = Form(None)):
    """Start research for the logged-in user."""
    session = require_user_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    customer_id = session.customer_id
    task_id = f"research_{customer_id}_{asyncio.get_event_loop().time()}"
    progress_store[task_id] = {"status": "starting", "message": "Starte Recherche...", "progress": 0}

    async def run_research():
        try:
            def progress_callback(message: str, step: int, total: int):
                progress_store[task_id] = {"status": "running", "message": message, "progress": int((step / total) * 100)}

            topics = await orchestrator.research_new_topics(
                UUID(customer_id),
                progress_callback=progress_callback,
                post_type_id=UUID(post_type_id) if post_type_id else None
            )
            progress_store[task_id] = {"status": "completed", "message": f"{len(topics)} Topics gefunden!", "progress": 100, "topics": topics}
        except Exception as e:
            logger.exception(f"Research failed: {e}")
            progress_store[task_id] = {"status": "error", "message": str(e), "progress": 0}

    background_tasks.add_task(run_research)
    return {"task_id": task_id}


@user_router.post("/api/posts")
async def create_post(request: Request, background_tasks: BackgroundTasks, topic_json: str = Form(...), post_type_id: str = Form(None)):
    """Create a new post for the logged-in user."""
    session = require_user_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    customer_id = session.customer_id
    task_id = f"post_{customer_id}_{asyncio.get_event_loop().time()}"
    progress_store[task_id] = {"status": "starting", "message": "Starte Post-Erstellung...", "progress": 0}
    topic = json.loads(topic_json)

    async def run_create_post():
        try:
            def progress_callback(message: str, iteration: int, max_iterations: int, score: int = None, versions: list = None, feedback_list: list = None):
                progress = int((iteration / max_iterations) * 100) if iteration > 0 else 5
                score_text = f" (Score: {score}/100)" if score else ""
                progress_store[task_id] = {
                    "status": "running", "message": f"{message}{score_text}", "progress": progress,
                    "iteration": iteration, "max_iterations": max_iterations,
                    "versions": versions or [], "feedback_list": feedback_list or []
                }

            result = await orchestrator.create_post(
                customer_id=UUID(customer_id), topic=topic, max_iterations=3,
                progress_callback=progress_callback,
                post_type_id=UUID(post_type_id) if post_type_id else None
            )
            progress_store[task_id] = {
                "status": "completed", "message": "Post erstellt!", "progress": 100,
                "result": {
                    "post_id": str(result["post_id"]), "final_post": result["final_post"],
                    "iterations": result["iterations"], "final_score": result["final_score"], "approved": result["approved"]
                }
            }
        except Exception as e:
            logger.exception(f"Post creation failed: {e}")
            progress_store[task_id] = {"status": "error", "message": str(e), "progress": 0}

    background_tasks.add_task(run_create_post)
    return {"task_id": task_id}
