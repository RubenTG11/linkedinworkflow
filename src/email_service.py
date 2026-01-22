"""Email service for sending posts via email."""
import base64
import html
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional
from loguru import logger

from src.config import settings


def _load_logo_base64() -> str:
    """Load and encode the logo as base64."""
    logo_path = Path(__file__).parent / "web" / "static" / "logo.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return ""


# Pre-load logo at module import
_LOGO_BASE64 = _load_logo_base64()


class EmailService:
    """Service for sending emails."""

    def __init__(self):
        """Initialize email service."""
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.from_name = settings.smtp_from_name

    def is_configured(self) -> bool:
        """Check if email is properly configured."""
        return bool(self.host and self.user and self.password)

    def send_post(
        self,
        recipient: str,
        post_content: str,
        topic_title: str,
        customer_name: str,
        score: Optional[int] = None
    ) -> bool:
        """
        Send a post via email.

        Args:
            recipient: Email address to send to
            post_content: The post content
            topic_title: Title of the topic
            customer_name: Name of the customer
            score: Optional critic score

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.error("Email not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD.")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Dein LinkedIn Post: {topic_title}"
            msg["From"] = f"onyva <{self.user}>"
            msg["To"] = recipient

            # Plain text version - just the post
            text_content = f"""{post_content}

--
onyva"""

            # HTML version - minimal, just post + onyva logo
            logo_html = ""
            if _LOGO_BASE64:
                logo_html = f'<img src="data:image/png;base64,{_LOGO_BASE64}" alt="onyva" style="height: 32px; width: auto;">'
            else:
                # Fallback if logo not found
                logo_html = '<span style="font-size: 14px; color: #666; font-weight: 500;">onyva</span>'

            # Convert newlines to <br> for email client compatibility
            post_html = html.escape(post_content).replace('\n', '<br>\n')

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #ffffff; margin: 0; padding: 40px 20px; color: #1a1a1a; }}
        .container {{ max-width: 560px; margin: 0 auto; }}
        .post {{ font-size: 15px; line-height: 1.7; color: #1a1a1a; margin-bottom: 40px; }}
        .footer {{ padding-top: 24px; border-top: 1px solid #e5e5e5; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="post">{post_html}</div>
        <div class="footer">
            {logo_html}
        </div>
    </div>
</body>
</html>
"""

            # Attach both versions
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # Send email
            context = ssl.create_default_context()

            with smtplib.SMTP(self.host, self.port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.user, self.password)
                server.sendmail(self.user, recipient, msg.as_string())

            logger.info(f"Email sent successfully to {recipient}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


# Global email service instance
email_service = EmailService()
