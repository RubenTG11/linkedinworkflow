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
from pydantic import BaseModel
from loguru import logger

from src.config import settings
from src.database import db
from src.orchestrator import orchestrator

# Setup
app = FastAPI(title="LinkedIn Post Creation System")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Store for progress updates (in production, use Redis or similar)
progress_store = {}

# Authentication
WEB_PASSWORD = settings.web_password
SESSION_SECRET = settings.session_secret or secrets.token_hex(32)
AUTH_COOKIE_NAME = "linkedin_auth"

def hash_password(password: str) -> str:
    """Hash password with session secret."""
    return hashlib.sha256(f"{password}{SESSION_SECRET}".encode()).hexdigest()

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
            customers_with_posts.append({
                "customer": customer,
                "posts": posts,
                "post_count": len(posts)
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
            customer_statuses.append({
                "customer": customer,
                "status": status
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
    style_guide: str = Form(None)
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

    async def run_setup():
        try:
            progress_store[task_id] = {"status": "running", "message": "Erstelle Kunde...", "progress": 10}
            await asyncio.sleep(0.1)

            progress_store[task_id] = {"status": "running", "message": "Scrape LinkedIn Posts...", "progress": 30}

            customer = await orchestrator.run_initial_setup(
                linkedin_url=linkedin_url,
                customer_name=name,
                customer_data=customer_data
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


@app.get("/api/customers/{customer_id}/topics")
async def get_customer_topics(customer_id: str):
    """Get all research topics for a customer."""
    try:
        all_research = await db.get_all_research(UUID(customer_id))
        all_topics = []

        for research in all_research:
            if research.suggested_topics:
                for topic in research.suggested_topics:
                    topic["research_id"] = str(research.id)
                    all_topics.append(topic)

        return {"topics": all_topics}
    except Exception as e:
        logger.error(f"Error loading topics: {e}")
        return {"topics": [], "error": str(e)}


@app.post("/api/research")
async def start_research(background_tasks: BackgroundTasks, customer_id: str = Form(...)):
    """Start research for a customer."""
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
                progress_callback=progress_callback
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
    topic_json: str = Form(...)
):
    """Create a new post."""
    task_id = f"post_{customer_id}_{asyncio.get_event_loop().time()}"
    progress_store[task_id] = {"status": "starting", "message": "Starte Post-Erstellung...", "progress": 0}

    topic = json.loads(topic_json)

    async def run_create_post():
        try:
            def progress_callback(message: str, iteration: int, max_iterations: int, score: int = None):
                progress = int((iteration / max_iterations) * 100) if iteration > 0 else 5
                score_text = f" (Score: {score}/100)" if score else ""
                progress_store[task_id] = {
                    "status": "running",
                    "message": f"{message}{score_text}",
                    "progress": progress,
                    "iteration": iteration,
                    "max_iterations": max_iterations
                }

            result = await orchestrator.create_post(
                customer_id=UUID(customer_id),
                topic=topic,
                max_iterations=3,
                progress_callback=progress_callback
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


def run_web():
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_web()
