"""FastAPI web frontend for LinkedIn Post Creation System."""
import asyncio
import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Request, Form, BackgroundTasks, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from loguru import logger

from src.config import settings
from src.database import db
from src.orchestrator import orchestrator
from src.email_service import email_service

# Setup
app = FastAPI(title="LinkedIn Post Creation System")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Store for progress updates (in production, use Redis or similar)
progress_store = {}

# Authentication
WEB_PASSWORD = settings.web_password
SESSION_SECRET = settings.session_secret or secrets.token_hex(32)
AUTH_COOKIE_NAME = "linkedin_auth"

def hash_password(password: str) -> str:
    """Hash password with session secret."""
    return hashlib.sha256(f"{password}{SESSION_SECRET}".encode()).hexdigest()


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

def verify_auth(request: Request) -> bool:
    """Check if request is authenticated."""
    if not WEB_PASSWORD:
        return True  # No password set, allow access
    cookie = request.cookies.get(AUTH_COOKIE_NAME)
    if not cookie:
        return False
    return cookie == hash_password(WEB_PASSWORD)

async def require_auth(request: Request):
    """Dependency to require authentication."""
    if not verify_auth(request):
        raise HTTPException(status_code=302, headers={"Location": "/login"})


# ==================== AUTH ROUTES ====================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Login page."""
    if not WEB_PASSWORD:
        return RedirectResponse(url="/", status_code=302)
    if verify_auth(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error
    })

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Handle login."""
    if password == WEB_PASSWORD:
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=hash_password(WEB_PASSWORD),
            httponly=True,
            max_age=60 * 60 * 24 * 7,  # 7 days
            samesite="lax"
        )
        return response
    return RedirectResponse(url="/login?error=invalid", status_code=302)

@app.get("/logout")
async def logout():
    """Handle logout."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


class CustomerCreate(BaseModel):
    name: str
    linkedin_url: str
    company_name: Optional[str] = None
    email: Optional[str] = None
    persona: Optional[str] = None
    form_of_address: Optional[str] = None
    style_guide: Optional[str] = None


# ==================== PAGES ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Dashboard home page."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    try:
        customers = await db.list_customers()
        total_posts = 0
        for customer in customers:
            posts = await db.get_generated_posts(customer.id)
            total_posts += len(posts)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "page": "home",
            "customers_count": len(customers),
            "total_posts": total_posts
        })
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "page": "home",
            "error": str(e)
        })


@app.get("/customers/new", response_class=HTMLResponse)
async def new_customer_page(request: Request):
    """New customer setup page."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("new_customer.html", {
        "request": request,
        "page": "new_customer"
    })


@app.get("/research", response_class=HTMLResponse)
async def research_page(request: Request):
    """Research topics page."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    customers = await db.list_customers()
    return templates.TemplateResponse("research.html", {
        "request": request,
        "page": "research",
        "customers": customers
    })


@app.get("/create", response_class=HTMLResponse)
async def create_post_page(request: Request):
    """Create post page."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    customers = await db.list_customers()
    return templates.TemplateResponse("create_post.html", {
        "request": request,
        "page": "create",
        "customers": customers
    })


@app.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request):
    """View all posts page."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    try:
        customers = await db.list_customers()
        customers_with_posts = []

        for customer in customers:
            posts = await db.get_generated_posts(customer.id)
            profile_picture = await get_customer_profile_picture(customer.id)
            customers_with_posts.append({
                "customer": customer,
                "posts": posts,
                "post_count": len(posts),
                "profile_picture": profile_picture
            })

        return templates.TemplateResponse("posts.html", {
            "request": request,
            "page": "posts",
            "customers_with_posts": customers_with_posts,
            "total_posts": sum(c["post_count"] for c in customers_with_posts)
        })
    except Exception as e:
        logger.error(f"Error loading posts: {e}")
        return templates.TemplateResponse("posts.html", {
            "request": request,
            "page": "posts",
            "customers_with_posts": [],
            "total_posts": 0,
            "error": str(e)
        })


@app.get("/posts/{post_id}", response_class=HTMLResponse)
async def post_detail_page(request: Request, post_id: str):
    """Detailed view of a single post."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    try:
        post = await db.get_generated_post(UUID(post_id))
        if not post:
            return RedirectResponse(url="/posts", status_code=302)

        # Get customer info
        customer = await db.get_customer(post.customer_id)

        # Get reference posts (LinkedIn posts used for style)
        linkedin_posts = await db.get_linkedin_posts(post.customer_id)
        reference_posts = [
            p.post_text for p in linkedin_posts
            if p.post_text and len(p.post_text) > 100
        ][:10]  # Show top 10 as reference

        # Extract profile picture from LinkedIn posts raw_data
        profile_picture_url = None
        for lp in linkedin_posts:
            if lp.raw_data and isinstance(lp.raw_data, dict):
                author = lp.raw_data.get("author", {})
                if author and isinstance(author, dict):
                    profile_picture_url = author.get("profile_picture")
                    if profile_picture_url:
                        break  # Found it, stop searching

        # Get profile analysis
        profile_analysis_record = await db.get_profile_analysis(post.customer_id)
        profile_analysis = profile_analysis_record.full_analysis if profile_analysis_record else None

        # Get post type analysis if a post type was used
        post_type = None
        post_type_analysis = None
        if post.post_type_id:
            post_type = await db.get_post_type(post.post_type_id)
            if post_type and post_type.analysis:
                post_type_analysis = post_type.analysis

        # Get final feedback
        final_feedback = None
        if post.critic_feedback and len(post.critic_feedback) > 0:
            final_feedback = post.critic_feedback[-1]

        return templates.TemplateResponse("post_detail.html", {
            "request": request,
            "page": "posts",
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


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """Customer status page."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    try:
        customers = await db.list_customers()
        customer_statuses = []

        for customer in customers:
            status = await orchestrator.get_customer_status(customer.id)
            profile_picture = await get_customer_profile_picture(customer.id)
            customer_statuses.append({
                "customer": customer,
                "status": status,
                "profile_picture": profile_picture
            })

        return templates.TemplateResponse("status.html", {
            "request": request,
            "page": "status",
            "customer_statuses": customer_statuses
        })
    except Exception as e:
        logger.error(f"Error loading status: {e}")
        return templates.TemplateResponse("status.html", {
            "request": request,
            "page": "status",
            "customer_statuses": [],
            "error": str(e)
        })


@app.get("/scraped-posts", response_class=HTMLResponse)
async def scraped_posts_page(request: Request):
    """Manage scraped LinkedIn posts - manual classification."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    customers = await db.list_customers()
    return templates.TemplateResponse("scraped_posts.html", {
        "request": request,
        "page": "scraped_posts",
        "customers": customers
    })


# ==================== API ENDPOINTS ====================

@app.post("/api/customers")
async def create_customer(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    linkedin_url: str = Form(...),
    company_name: str = Form(None),
    email: str = Form(None),
    persona: str = Form(None),
    form_of_address: str = Form(None),
    style_guide: str = Form(None),
    post_types_json: str = Form(None)
):
    """Create a new customer and run initial setup."""
    task_id = f"setup_{name}_{asyncio.get_event_loop().time()}"
    progress_store[task_id] = {"status": "starting", "message": "Starte Setup...", "progress": 0}

    customer_data = {
        "company_name": company_name,
        "email": email,
        "persona": persona,
        "form_of_address": form_of_address,
        "style_guide": style_guide,
        "topic_history": [],
        "example_posts": []
    }

    # Parse post types if provided
    post_types_data = None
    if post_types_json:
        try:
            post_types_data = json.loads(post_types_json)
        except json.JSONDecodeError:
            logger.warning("Failed to parse post_types_json")

    async def run_setup():
        try:
            progress_store[task_id] = {"status": "running", "message": "Erstelle Kunde...", "progress": 10}
            await asyncio.sleep(0.1)

            progress_store[task_id] = {"status": "running", "message": "Scrape LinkedIn Posts...", "progress": 30}

            customer = await orchestrator.run_initial_setup(
                linkedin_url=linkedin_url,
                customer_name=name,
                customer_data=customer_data,
                post_types_data=post_types_data
            )

            progress_store[task_id] = {
                "status": "completed",
                "message": "Setup abgeschlossen!",
                "progress": 100,
                "customer_id": str(customer.id)
            }
        except Exception as e:
            logger.exception(f"Setup failed: {e}")
            progress_store[task_id] = {"status": "error", "message": str(e), "progress": 0}

    background_tasks.add_task(run_setup)
    return {"task_id": task_id}


@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get task progress."""
    return progress_store.get(task_id, {"status": "unknown", "message": "Task not found"})


@app.get("/api/customers/{customer_id}/post-types")
async def get_customer_post_types(customer_id: str):
    """Get post types for a customer."""
    try:
        post_types = await db.get_post_types(UUID(customer_id))
        return {
            "post_types": [
                {
                    "id": str(pt.id),
                    "name": pt.name,
                    "description": pt.description,
                    "identifying_hashtags": pt.identifying_hashtags,
                    "identifying_keywords": pt.identifying_keywords,
                    "semantic_properties": pt.semantic_properties,
                    "has_analysis": pt.analysis is not None,
                    "analyzed_post_count": pt.analyzed_post_count,
                    "is_active": pt.is_active
                }
                for pt in post_types
            ]
        }
    except Exception as e:
        logger.error(f"Error loading post types: {e}")
        return {"post_types": [], "error": str(e)}


@app.get("/api/customers/{customer_id}/linkedin-posts")
async def get_customer_linkedin_posts(customer_id: str):
    """Get all scraped LinkedIn posts for a customer."""
    try:
        logger.info(f"Loading LinkedIn posts for customer: {customer_id}")
        posts = await db.get_linkedin_posts(UUID(customer_id))
        logger.info(f"Found {len(posts)} LinkedIn posts")

        result_posts = []
        for post in posts:
            try:
                result_posts.append({
                    "id": str(post.id),
                    "post_text": post.post_text,
                    "post_url": post.post_url,
                    "posted_at": post.post_date.isoformat() if post.post_date else None,
                    "engagement_score": (post.likes or 0) + (post.comments or 0) + (post.shares or 0),
                    "likes": post.likes,
                    "comments": post.comments,
                    "shares": post.shares,
                    "post_type_id": str(post.post_type_id) if post.post_type_id else None,
                    "classification_method": post.classification_method,
                    "classification_confidence": post.classification_confidence
                })
            except Exception as post_error:
                logger.error(f"Error processing post {post.id}: {post_error}")

        return {
            "posts": result_posts,
            "total": len(result_posts)
        }
    except Exception as e:
        logger.exception(f"Error loading LinkedIn posts: {e}")
        return {"posts": [], "total": 0, "error": str(e)}


class ClassifyPostRequest(BaseModel):
    """Request model for classifying a post."""
    post_type_id: Optional[str] = None


@app.patch("/api/linkedin-posts/{post_id}/classify")
async def classify_linkedin_post(post_id: str, request: ClassifyPostRequest):
    """Manually classify a LinkedIn post to a post type."""
    try:
        if request.post_type_id:
            await db.update_post_classification(
                post_id=UUID(post_id),
                post_type_id=UUID(request.post_type_id),
                classification_method="manual",
                classification_confidence=1.0
            )
        else:
            # Remove classification - set to null
            await asyncio.to_thread(
                lambda: db.client.table("linkedin_posts").update({
                    "post_type_id": None,
                    "classification_method": None,
                    "classification_confidence": None
                }).eq("id", post_id).execute()
            )

        return {"success": True, "post_id": post_id}
    except Exception as e:
        logger.error(f"Error classifying post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/customers/{customer_id}/classify-posts")
async def classify_customer_posts(customer_id: str, background_tasks: BackgroundTasks):
    """Trigger post classification for a customer."""
    task_id = f"classify_{customer_id}_{asyncio.get_event_loop().time()}"
    progress_store[task_id] = {"status": "starting", "message": "Starte Klassifizierung...", "progress": 0}

    async def run_classification():
        try:
            progress_store[task_id] = {"status": "running", "message": "Klassifiziere Posts...", "progress": 50}
            count = await orchestrator.classify_posts(UUID(customer_id))
            progress_store[task_id] = {
                "status": "completed",
                "message": f"{count} Posts klassifiziert",
                "progress": 100,
                "classified_count": count
            }
        except Exception as e:
            logger.exception(f"Classification failed: {e}")
            progress_store[task_id] = {"status": "error", "message": str(e), "progress": 0}

    background_tasks.add_task(run_classification)
    return {"task_id": task_id}


@app.post("/api/customers/{customer_id}/analyze-post-types")
async def analyze_customer_post_types(customer_id: str, background_tasks: BackgroundTasks):
    """Trigger post type analysis for a customer."""
    task_id = f"analyze_{customer_id}_{asyncio.get_event_loop().time()}"
    progress_store[task_id] = {"status": "starting", "message": "Starte Analyse...", "progress": 0}

    async def run_analysis():
        try:
            progress_store[task_id] = {"status": "running", "message": "Analysiere Post-Typen...", "progress": 50}
            results = await orchestrator.analyze_post_types(UUID(customer_id))
            analyzed_count = sum(1 for r in results.values() if r.get("sufficient_data"))
            progress_store[task_id] = {
                "status": "completed",
                "message": f"{analyzed_count} Post-Typen analysiert",
                "progress": 100,
                "results": results
            }
        except Exception as e:
            logger.exception(f"Analysis failed: {e}")
            progress_store[task_id] = {"status": "error", "message": str(e), "progress": 0}

    background_tasks.add_task(run_analysis)
    return {"task_id": task_id}


@app.get("/api/customers/{customer_id}/topics")
async def get_customer_topics(
    customer_id: str,
    include_used: bool = False,
    post_type_id: str = None
):
    """Get research topics for a customer, excluding already used ones by default."""
    try:
        # Filter research by post type if specified
        if post_type_id:
            all_research = await db.get_all_research(UUID(customer_id), UUID(post_type_id))
        else:
            all_research = await db.get_all_research(UUID(customer_id))

        # Get already used topic titles (from generated posts)
        used_topic_titles = set()
        if not include_used:
            generated_posts = await db.get_generated_posts(UUID(customer_id))
            for post in generated_posts:
                if post.topic_title:
                    # Normalize title for comparison (lowercase, strip)
                    used_topic_titles.add(post.topic_title.lower().strip())

        all_topics = []
        for research in all_research:
            if research.suggested_topics:
                for topic in research.suggested_topics:
                    topic_title = topic.get("title", "").lower().strip()

                    # Skip if topic was already used for a post
                    if topic_title in used_topic_titles:
                        continue

                    topic["research_id"] = str(research.id)
                    topic["target_post_type_id"] = str(research.target_post_type_id) if research.target_post_type_id else None
                    all_topics.append(topic)

        return {
            "topics": all_topics,
            "used_count": len(used_topic_titles),
            "available_count": len(all_topics)
        }
    except Exception as e:
        logger.error(f"Error loading topics: {e}")
        return {"topics": [], "error": str(e)}


@app.post("/api/research")
async def start_research(
    background_tasks: BackgroundTasks,
    customer_id: str = Form(...),
    post_type_id: str = Form(None)
):
    """Start research for a customer, optionally targeting a specific post type."""
    task_id = f"research_{customer_id}_{asyncio.get_event_loop().time()}"
    progress_store[task_id] = {"status": "starting", "message": "Starte Recherche...", "progress": 0}

    async def run_research():
        try:
            def progress_callback(message: str, step: int, total: int):
                progress_store[task_id] = {
                    "status": "running",
                    "message": message,
                    "progress": int((step / total) * 100)
                }

            topics = await orchestrator.research_new_topics(
                UUID(customer_id),
                progress_callback=progress_callback,
                post_type_id=UUID(post_type_id) if post_type_id else None
            )

            progress_store[task_id] = {
                "status": "completed",
                "message": f"{len(topics)} Topics gefunden!",
                "progress": 100,
                "topics": topics
            }
        except Exception as e:
            logger.exception(f"Research failed: {e}")
            progress_store[task_id] = {"status": "error", "message": str(e), "progress": 0}

    background_tasks.add_task(run_research)
    return {"task_id": task_id}


@app.post("/api/posts")
async def create_post(
    background_tasks: BackgroundTasks,
    customer_id: str = Form(...),
    topic_json: str = Form(...),
    post_type_id: str = Form(None)
):
    """Create a new post, optionally using a specific post type."""
    task_id = f"post_{customer_id}_{asyncio.get_event_loop().time()}"
    progress_store[task_id] = {"status": "starting", "message": "Starte Post-Erstellung...", "progress": 0}

    topic = json.loads(topic_json)

    async def run_create_post():
        try:
            def progress_callback(message: str, iteration: int, max_iterations: int, score: int = None,
                                versions: list = None, feedback_list: list = None):
                progress = int((iteration / max_iterations) * 100) if iteration > 0 else 5
                score_text = f" (Score: {score}/100)" if score else ""
                progress_store[task_id] = {
                    "status": "running",
                    "message": f"{message}{score_text}",
                    "progress": progress,
                    "iteration": iteration,
                    "max_iterations": max_iterations,
                    "versions": versions or [],
                    "feedback_list": feedback_list or []
                }

            result = await orchestrator.create_post(
                customer_id=UUID(customer_id),
                topic=topic,
                max_iterations=3,
                progress_callback=progress_callback,
                post_type_id=UUID(post_type_id) if post_type_id else None
            )

            progress_store[task_id] = {
                "status": "completed",
                "message": "Post erstellt!",
                "progress": 100,
                "result": {
                    "post_id": str(result["post_id"]),
                    "final_post": result["final_post"],
                    "iterations": result["iterations"],
                    "final_score": result["final_score"],
                    "approved": result["approved"]
                }
            }
        except Exception as e:
            logger.exception(f"Post creation failed: {e}")
            progress_store[task_id] = {"status": "error", "message": str(e), "progress": 0}

    background_tasks.add_task(run_create_post)
    return {"task_id": task_id}


@app.get("/api/posts")
async def get_all_posts():
    """API endpoint to get all posts as JSON."""
    customers = await db.list_customers()
    all_posts = []

    for customer in customers:
        posts = await db.get_generated_posts(customer.id)
        for post in posts:
            all_posts.append({
                "id": str(post.id),
                "customer_name": customer.name,
                "topic_title": post.topic_title,
                "content": post.post_content,
                "iterations": post.iterations,
                "status": post.status,
                "created_at": post.created_at.isoformat() if post.created_at else None
            })

    return {"posts": all_posts, "total": len(all_posts)}


class EmailRequest(BaseModel):
    """Request model for sending email."""
    recipient: str
    post_id: str


@app.get("/api/email/config")
async def get_email_config(request: Request):
    """Check if email is configured and get default recipient."""
    if not verify_auth(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "configured": email_service.is_configured(),
        "default_recipient": settings.email_default_recipient or ""
    }


@app.post("/api/email/send")
async def send_post_email(request: Request, email_request: EmailRequest):
    """Send a post via email."""
    if not verify_auth(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not email_service.is_configured():
        raise HTTPException(status_code=400, detail="E-Mail ist nicht konfiguriert. Bitte SMTP-Einstellungen in .env setzen.")

    try:
        post = await db.get_generated_post(UUID(email_request.post_id))
        if not post:
            raise HTTPException(status_code=404, detail="Post nicht gefunden")

        customer = await db.get_customer(post.customer_id)

        # Get final score
        score = None
        if post.critic_feedback and len(post.critic_feedback) > 0:
            score = post.critic_feedback[-1].get("overall_score")

        success = email_service.send_post(
            recipient=email_request.recipient,
            post_content=post.post_content,
            topic_title=post.topic_title or "LinkedIn Post",
            customer_name=customer.name if customer else "Unbekannt",
            score=score
        )

        if success:
            return {"success": True, "message": f"E-Mail wurde an {email_request.recipient} gesendet"}
        else:
            raise HTTPException(status_code=500, detail="E-Mail konnte nicht gesendet werden. Prüfe die SMTP-Einstellungen.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Senden: {str(e)}")


def run_web():
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_web()
