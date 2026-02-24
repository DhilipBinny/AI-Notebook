"""
Email service for sending invitation emails via SMTP.
"""

import asyncio
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Async email service using aiosmtplib."""

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.smtp_host)

    @staticmethod
    async def send_email(to: str, subject: str, html_body: str, text_body: str) -> None:
        if not EmailService.is_configured():
            logger.warning("SMTP not configured — skipping email to %s", to)
            return

        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_from or settings.smtp_user
        msg["To"] = to
        msg["Subject"] = subject

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            # Port 465 = implicit TLS (use_tls), port 587 = STARTTLS (start_tls)
            use_tls = settings.smtp_tls and settings.smtp_port == 465
            start_tls = settings.smtp_tls and settings.smtp_port != 465
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                use_tls=use_tls,
                start_tls=start_tls,
            )
            logger.info("Email sent to %s: %s", to, subject)
        except Exception:
            logger.exception("Failed to send email to %s", to)

    @staticmethod
    async def send_invitation(
        email: str,
        invite_code: str,
        note: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        base_url: Optional[str] = None,
    ) -> None:
        from urllib.parse import quote
        origin = base_url.rstrip("/")
        invite_link = f"{origin}/auth/register?invite={invite_code}&email={quote(email)}"

        html_body = EmailService._build_invitation_html(invite_link, note, expires_at)
        text_body = EmailService._build_invitation_text(invite_link, note, expires_at)

        await EmailService.send_email(
            to=email,
            subject="You're invited to AI Notebook",
            html_body=html_body,
            text_body=text_body,
        )

    @staticmethod
    def send_invitation_background(
        email: str,
        invite_code: str,
        note: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Fire-and-forget: schedule invitation email as a background task."""
        asyncio.create_task(
            EmailService.send_invitation(email, invite_code, note, expires_at, base_url)
        )

    @staticmethod
    def _build_invitation_html(
        invite_link: str, note: Optional[str], expires_at: Optional[datetime]
    ) -> str:
        note_block = ""
        if note:
            note_block = f"""
              <tr>
                <td style="padding: 0 0 20px 0;">
                  <p style="margin: 0; padding: 12px 16px; background-color: #f8f9fa; border-left: 3px solid #4a90d9; color: #555555; font-size: 14px; line-height: 1.5;">{note}</p>
                </td>
              </tr>"""

        expires_block = ""
        if expires_at:
            expires_str = expires_at.strftime("%B %d, %Y")
            expires_block = f"""
              <tr>
                <td style="padding: 0 0 20px 0;">
                  <p style="margin: 0; color: #999999; font-size: 13px;">This invitation expires on {expires_str}.</p>
                </td>
              </tr>"""

        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f5;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px;">
          <tr>
            <td style="padding: 40px 40px 0 40px;">
              <h1 style="margin: 0 0 8px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">You've been invited</h1>
              <p style="margin: 0 0 24px 0; color: #666666; font-size: 15px; line-height: 1.5;">An administrator has invited you to create an account on AI Notebook.</p>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                {note_block}
                <tr>
                  <td style="padding: 0 0 24px 0;">
                    <a href="{invite_link}" style="display: inline-block; padding: 12px 24px; background-color: #4a90d9; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500; font-size: 14px;">Create your account</a>
                  </td>
                </tr>
                {expires_block}
                <tr>
                  <td style="padding: 0 0 32px 0;">
                    <p style="margin: 0; color: #999999; font-size: 12px; line-height: 1.5;">If the button doesn't work, copy and paste this link into your browser:</p>
                    <p style="margin: 4px 0 0 0; word-break: break-all;"><a href="{invite_link}" style="color: #4a90d9; font-size: 12px; text-decoration: none;">{invite_link}</a></p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 20px 40px; border-top: 1px solid #eeeeee;">
              <p style="margin: 0; color: #999999; font-size: 12px;">AI Notebook</p>
            </td>
          </tr>
        </table>
        <table role="presentation" width="480" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding: 20px 40px 0 40px;">
              <p style="margin: 0; color: #bbbbbb; font-size: 11px; line-height: 1.5;">You received this email because an administrator invited you to AI Notebook. If you did not expect this, you can ignore it.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    @staticmethod
    async def send_password_reset(email: str, reset_link: str) -> None:
        html_body = EmailService._build_password_reset_html(reset_link)
        text_body = EmailService._build_password_reset_text(reset_link)
        await EmailService.send_email(
            to=email,
            subject="Reset your password — AI Notebook",
            html_body=html_body,
            text_body=text_body,
        )

    @staticmethod
    def send_password_reset_background(email: str, reset_link: str) -> None:
        """Fire-and-forget: schedule password reset email as a background task."""
        asyncio.create_task(
            EmailService.send_password_reset(email, reset_link)
        )

    @staticmethod
    def _build_password_reset_html(reset_link: str) -> str:
        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f5;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px;">
          <tr>
            <td style="padding: 40px 40px 0 40px;">
              <h1 style="margin: 0 0 8px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Reset your password</h1>
              <p style="margin: 0 0 24px 0; color: #666666; font-size: 15px; line-height: 1.5;">We received a request to reset your AI Notebook password. Click the button below to choose a new one.</p>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding: 0 0 24px 0;">
                    <a href="{reset_link}" style="display: inline-block; padding: 12px 24px; background-color: #4a90d9; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500; font-size: 14px;">Reset password</a>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 0 0 20px 0;">
                    <p style="margin: 0; color: #e74c3c; font-size: 13px; font-weight: 500;">This link expires in 10 minutes.</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 0 0 32px 0;">
                    <p style="margin: 0; color: #999999; font-size: 12px; line-height: 1.5;">If the button doesn't work, copy and paste this link into your browser:</p>
                    <p style="margin: 4px 0 0 0; word-break: break-all;"><a href="{reset_link}" style="color: #4a90d9; font-size: 12px; text-decoration: none;">{reset_link}</a></p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 20px 40px; border-top: 1px solid #eeeeee;">
              <p style="margin: 0; color: #999999; font-size: 12px;">AI Notebook</p>
            </td>
          </tr>
        </table>
        <table role="presentation" width="480" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding: 20px 40px 0 40px;">
              <p style="margin: 0; color: #bbbbbb; font-size: 11px; line-height: 1.5;">If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    @staticmethod
    def _build_password_reset_text(reset_link: str) -> str:
        return "\n".join([
            "Reset your password",
            "",
            "We received a request to reset your AI Notebook password.",
            "",
            "Reset your password:",
            reset_link,
            "",
            "This link expires in 10 minutes.",
            "",
            "---",
            "AI Notebook",
            "",
            "If you didn't request a password reset, you can safely ignore this email.",
        ])

    @staticmethod
    def _build_invitation_text(
        invite_link: str, note: Optional[str], expires_at: Optional[datetime]
    ) -> str:
        lines = [
            "You've been invited to AI Notebook",
            "",
            "An administrator has invited you to create an account.",
            "",
        ]
        if note:
            lines += [f"> {note}", ""]
        lines += [
            "Create your account:",
            invite_link,
            "",
        ]
        if expires_at:
            expires_str = expires_at.strftime("%B %d, %Y")
            lines += [f"This invitation expires on {expires_str}.", ""]
        lines += [
            "---",
            "AI Notebook",
            "",
            "You received this email because an administrator invited you.",
            "If you did not expect this, you can ignore it.",
        ]
        return "\n".join(lines)
