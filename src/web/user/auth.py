"""User authentication with Supabase LinkedIn OAuth."""
import re
import secrets
from typing import Optional
from uuid import UUID

from fastapi import Request, Response
from loguru import logger

from src.config import settings
from src.database import db

# Session management
USER_SESSION_COOKIE = "linkedin_user_session"
SESSION_SECRET = settings.session_secret or secrets.token_hex(32)


def normalize_linkedin_url(url: str) -> str:
    """Normalize LinkedIn URL for comparison.

    Extracts the username/vanityName from various LinkedIn URL formats.
    """
    if not url:
        return ""
    # Match linkedin.com/in/username with optional trailing slash or query params
    match = re.search(r'linkedin\.com/in/([^/?]+)', url.lower())
    if match:
        return match.group(1).rstrip('/')
    return url.lower().strip()


async def get_customer_by_vanity_name(vanity_name: str) -> Optional[dict]:
    """Find customer by LinkedIn vanityName.

    Constructs the LinkedIn URL from vanityName and matches against
    Customer.linkedin_url (normalized).
    """
    if not vanity_name:
        return None

    normalized_vanity = normalize_linkedin_url(f"https://www.linkedin.com/in/{vanity_name}/")

    # Get all customers and match
    customers = await db.list_customers()
    for customer in customers:
        customer_vanity = normalize_linkedin_url(customer.linkedin_url)
        if customer_vanity == normalized_vanity:
            return {
                "id": str(customer.id),
                "name": customer.name,
                "linkedin_url": customer.linkedin_url,
                "company_name": customer.company_name,
                "email": customer.email
            }

    return None


async def get_customer_by_email(email: str) -> Optional[dict]:
    """Find customer by email address.

    Fallback matching when LinkedIn vanityName is not available.
    """
    if not email:
        return None

    email_lower = email.lower().strip()

    # Get all customers and match by email
    customers = await db.list_customers()
    for customer in customers:
        if customer.email and customer.email.lower().strip() == email_lower:
            return {
                "id": str(customer.id),
                "name": customer.name,
                "linkedin_url": customer.linkedin_url,
                "company_name": customer.company_name,
                "email": customer.email
            }

    return None


async def get_customer_by_name(name: str) -> Optional[dict]:
    """Find customer by name.

    Fallback matching when email is not available.
    Tries exact match first, then case-insensitive.
    """
    if not name:
        return None

    name_lower = name.lower().strip()

    # Get all customers and match by name
    customers = await db.list_customers()

    # First try exact match
    for customer in customers:
        if customer.name == name:
            return {
                "id": str(customer.id),
                "name": customer.name,
                "linkedin_url": customer.linkedin_url,
                "company_name": customer.company_name,
                "email": customer.email
            }

    # Then try case-insensitive
    for customer in customers:
        if customer.name.lower().strip() == name_lower:
            return {
                "id": str(customer.id),
                "name": customer.name,
                "linkedin_url": customer.linkedin_url,
                "company_name": customer.company_name,
                "email": customer.email
            }

    return None


class UserSession:
    """User session data."""

    def __init__(
        self,
        customer_id: str,
        customer_name: str,
        linkedin_vanity_name: str,
        linkedin_name: Optional[str] = None,
        linkedin_picture: Optional[str] = None,
        email: Optional[str] = None
    ):
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.linkedin_vanity_name = linkedin_vanity_name
        self.linkedin_name = linkedin_name
        self.linkedin_picture = linkedin_picture
        self.email = email

    def to_cookie_value(self) -> str:
        """Serialize session to cookie value."""
        import json
        import hashlib

        data = {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "linkedin_vanity_name": self.linkedin_vanity_name,
            "linkedin_name": self.linkedin_name,
            "linkedin_picture": self.linkedin_picture,
            "email": self.email
        }

        # Create signed cookie value
        json_data = json.dumps(data)
        signature = hashlib.sha256(f"{json_data}{SESSION_SECRET}".encode()).hexdigest()[:16]

        import base64
        encoded = base64.b64encode(json_data.encode()).decode()
        return f"{encoded}.{signature}"

    @classmethod
    def from_cookie_value(cls, cookie_value: str) -> Optional["UserSession"]:
        """Deserialize session from cookie value."""
        import json
        import hashlib
        import base64

        try:
            parts = cookie_value.split(".")
            if len(parts) != 2:
                return None

            encoded, signature = parts
            json_data = base64.b64decode(encoded.encode()).decode()

            # Verify signature
            expected_sig = hashlib.sha256(f"{json_data}{SESSION_SECRET}".encode()).hexdigest()[:16]
            if signature != expected_sig:
                logger.warning("Invalid session signature")
                return None

            data = json.loads(json_data)
            return cls(
                customer_id=data["customer_id"],
                customer_name=data["customer_name"],
                linkedin_vanity_name=data["linkedin_vanity_name"],
                linkedin_name=data.get("linkedin_name"),
                linkedin_picture=data.get("linkedin_picture"),
                email=data.get("email")
            )
        except Exception as e:
            logger.error(f"Failed to parse session cookie: {e}")
            return None


def get_user_session(request: Request) -> Optional[UserSession]:
    """Get user session from request cookies."""
    cookie = request.cookies.get(USER_SESSION_COOKIE)
    if not cookie:
        return None
    return UserSession.from_cookie_value(cookie)


def set_user_session(response: Response, session: UserSession) -> None:
    """Set user session cookie."""
    response.set_cookie(
        key=USER_SESSION_COOKIE,
        value=session.to_cookie_value(),
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 days
        samesite="lax"
    )


def clear_user_session(response: Response) -> None:
    """Clear user session cookie."""
    response.delete_cookie(USER_SESSION_COOKIE)


async def handle_oauth_callback(
    access_token: str,
    refresh_token: Optional[str] = None
) -> Optional[UserSession]:
    """Handle OAuth callback from Supabase.

    1. Get user info from Supabase using access token
    2. Extract LinkedIn vanityName from user metadata
    3. Match with Customer record
    4. Create session if match found

    Returns UserSession if authorized, None if not.
    """
    from supabase import create_client

    try:
        # Create a new client with the user's access token
        supabase = create_client(settings.supabase_url, settings.supabase_key)

        # Get user info using the access token
        user_response = supabase.auth.get_user(access_token)

        if not user_response or not user_response.user:
            logger.error("Failed to get user from Supabase")
            return None

        user = user_response.user
        user_metadata = user.user_metadata or {}

        # Debug: Log full response
        import json
        logger.info(f"=== FULL OAUTH RESPONSE ===")
        logger.info(f"user.id: {user.id}")
        logger.info(f"user.email: {user.email}")
        logger.info(f"user.phone: {user.phone}")
        logger.info(f"user.app_metadata: {json.dumps(user.app_metadata, indent=2)}")
        logger.info(f"user.user_metadata: {json.dumps(user.user_metadata, indent=2)}")
        logger.info(f"--- Einzelne Felder ---")
        logger.info(f"given_name: {user_metadata.get('given_name')}")
        logger.info(f"family_name: {user_metadata.get('family_name')}")
        logger.info(f"name: {user_metadata.get('name')}")
        logger.info(f"email (metadata): {user_metadata.get('email')}")
        logger.info(f"picture: {user_metadata.get('picture')}")
        logger.info(f"sub: {user_metadata.get('sub')}")
        logger.info(f"provider_id: {user_metadata.get('provider_id')}")
        logger.info(f"=== END OAUTH RESPONSE ===")

        # LinkedIn OIDC provides these fields
        vanity_name = user_metadata.get("vanityName")  # LinkedIn username (often not provided)
        name = user_metadata.get("name")
        picture = user_metadata.get("picture")
        email = user.email

        logger.info(f"OAuth callback for user: {name} (vanityName={vanity_name}, email={email})")

        # Try to match with customer
        customer = None

        # First try vanityName if available
        if vanity_name:
            customer = await get_customer_by_vanity_name(vanity_name)
            if customer:
                logger.info(f"Matched by vanityName: {vanity_name}")

        # Fallback to email matching
        if not customer and email:
            customer = await get_customer_by_email(email)
            if customer:
                logger.info(f"Matched by email: {email}")

        # Fallback to name matching
        if not customer and name:
            customer = await get_customer_by_name(name)
            if customer:
                logger.info(f"Matched by name: {name}")

        if not customer:
            # Debug: List all customers to help diagnose
            all_customers = await db.list_customers()
            logger.warning(f"No customer found for LinkedIn user: {name} (email={email}, vanityName={vanity_name})")
            logger.warning(f"Available customers:")
            for c in all_customers:
                logger.warning(f"  - {c.name}: email={c.email}, linkedin={c.linkedin_url}")
            return None

        logger.info(f"User {name} matched with customer {customer['name']}")

        # Use vanityName from OAuth or extract from customer's linkedin_url
        effective_vanity_name = vanity_name
        if not effective_vanity_name and customer.get("linkedin_url"):
            effective_vanity_name = normalize_linkedin_url(customer["linkedin_url"])

        return UserSession(
            customer_id=customer["id"],
            customer_name=customer["name"],
            linkedin_vanity_name=effective_vanity_name or "",
            linkedin_name=name,
            linkedin_picture=picture,
            email=email
        )

    except Exception as e:
        logger.exception(f"OAuth callback error: {e}")
        return None


def get_supabase_login_url(redirect_to: str) -> str:
    """Generate Supabase OAuth login URL for LinkedIn.

    Args:
        redirect_to: The URL to redirect to after OAuth (the callback endpoint)

    Returns:
        The Supabase OAuth URL to redirect the user to
    """
    from urllib.parse import urlencode

    # Supabase OAuth endpoint
    base_url = f"{settings.supabase_url}/auth/v1/authorize"

    params = {
        "provider": "linkedin_oidc",
        "redirect_to": redirect_to
    }

    return f"{base_url}?{urlencode(params)}"
