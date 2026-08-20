"""
NOD 2.0 - Email System
Sends transactional emails (Welcome, Alerts, etc.)
Supports: Gmail SMTP (FREE), Brevo, SendGrid
"""
import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Email configuration (from .env)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "NOD AI <noreply@nod.ai>")

# API-based providers
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")


def _get_welcome_template(name: str) -> str:
    """HTML welcome email template"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to NOD 2.0</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center; }}
        .header h1 {{ color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; }}
        .header p {{ color: rgba(255,255,255,0.9); margin: 10px 0 0; font-size: 16px; }}
        .content {{ padding: 40px 30px; }}
        .greeting {{ font-size: 20px; color: #1a1a2e; margin-bottom: 20px; }}
        .greeting span {{ color: #667eea; font-weight: 700; }}
        .intro {{ color: #4a4a68; line-height: 1.7; font-size: 15px; margin-bottom: 30px; }}
        .features {{ margin: 30px 0; }}
        .feature {{ display: flex; align-items: flex-start; margin-bottom: 20px; padding: 18px; background: #f8f9ff; border-radius: 10px; border-left: 4px solid #667eea; }}
        .feature-icon {{ font-size: 24px; margin-right: 15px; min-width: 30px; text-align: center; }}
        .feature-text {{ flex: 1; }}
        .feature-title {{ font-weight: 700; color: #1a1a2e; font-size: 15px; margin-bottom: 5px; }}
        .feature-desc {{ color: #6b6b8a; font-size: 14px; line-height: 1.5; }}
        .security-box {{ background: linear-gradient(135deg, #fff5f5 0%, #fff0f0 100%); border: 1px solid #fed7d7; border-radius: 10px; padding: 20px; margin: 25px 0; }}
        .security-box h3 {{ color: #c53030; margin: 0 0 10px; font-size: 16px; }}
        .security-box p {{ color: #744210; font-size: 14px; margin: 0; line-height: 1.6; }}
        .cta {{ text-align: center; margin: 35px 0 25px; }}
        .cta a {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; padding: 14px 35px; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 15px rgba(102,126,234,0.4); }}
        .footer {{ background: #f8f9fa; padding: 25px 30px; text-align: center; border-top: 1px solid #e8e8e8; }}
        .footer p {{ color: #8a8a9a; font-size: 13px; margin: 5px 0; }}
        .footer .brand {{ font-weight: 700; color: #667eea; }}
        .tag {{ display: inline-block; background: #667eea; color: white; font-size: 11px; padding: 3px 10px; border-radius: 20px; margin-left: 8px; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Welcome to NOD 2.0</h1>
            <p>Your Secure AI Assistant</p>
        </div>
        
        <div class="content">
            <div class="greeting">Hey <span>{name}</span>! 👋</div>
            
            <div class="intro">
                Welcome aboard! You've just unlocked <strong>NOD 2.0</strong> — your personal, secure AI assistant that runs entirely on your machine. Your data never leaves your control.
            </div>
            
            <div class="features">
                <div class="feature">
                    <div class="feature-icon">💬</div>
                    <div class="feature-text">
                        <div class="feature-title">AI Chat with Ollama</div>
                        <div class="feature-desc">Chat with powerful local AI models. No internet needed. Your conversations stay private, always.</div>
                    </div>
                </div>
                
                <div class="feature">
                    <div class="feature-icon">🛡️</div>
                    <div class="feature-text">
                        <div class="feature-title">Bank-Level Security</div>
                        <div class="feature-desc">bcrypt passwords, JWT tokens, AES-256 encrypted vault for sensitive files, and full audit logging.</div>
                    </div>
                </div>
                
                <div class="feature">
                    <div class="feature-icon">🔍</div>
                    <div class="feature-text">
                        <div class="feature-title">Sensitive Data Scanner</div>
                        <div class="feature-desc">Auto-detects PAN, Aadhaar, bank details & passwords. Critical files are locked in an encrypted vault.</div>
                    </div>
                </div>
                
                <div class="feature">
                    <div class="feature-icon">📁</div>
                    <div class="feature-text">
                        <div class="feature-title">Smart File Manager</div>
                        <div class="feature-desc">"Show me my invoices" — NOD understands your files. Sandboxed access means it can never harm your system.</div>
                    </div>
                </div>
                
                <div class="feature">
                    <div class="feature-icon">🎙️</div>
                    <div class="feature-text">
                        <div class="feature-title">Voice Commands <span class="tag">COMING SOON</span></div>
                        <div class="feature-desc">Just say "Hey NOD" and control everything with your voice. Speech-to-text & text-to-speech included.</div>
                    </div>
                </div>
                
                <div class="feature">
                    <div class="feature-icon">🧠</div>
                    <div class="feature-text">
                        <div class="feature-title">Personal Brain (RAG) <span class="tag">COMING SOON</span></div>
                        <div class="feature-desc">Train NOD on YOUR documents. It will answer from your files, not just general knowledge.</div>
                    </div>
                </div>
                
                <div class="feature">
                    <div class="feature-icon">⚡</div>
                    <div class="feature-text">
                        <div class="feature-title">System Integration <span class="tag">COMING SOON</span></div>
                        <div class="feature-desc">Launch apps, monitor CPU/RAM, organize downloads, and get proactive alerts. Your PC's new brain.</div>
                    </div>
                </div>
            </div>
            
            <div class="security-box">
                <h3>🔐 Your Security Promise</h3>
                <p>NOD will <strong>never</strong> delete files without double confirmation. <strong>Never</strong> install software without your explicit "Yes". <strong>Never</strong> train on your personal data without permission. Every action is logged — full transparency.</p>
            </div>
            
            <div class="cta">
                <a href="http://127.0.0.1:5000/chat">Start Chatting →</a>
            </div>
        </div>
        
        <div class="footer">
            <p class="brand">NOD 2.0 — Your Data, Your Control</p>
            <p>This email was sent because you signed up for NOD AI Assistant.</p>
            <p>© {datetime.now().year} NOD AI. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""


def send_email_smtp(to_email: str, subject: str, html_body: str, text_body: str = "") -> dict:
    """Send email via SMTP (Gmail, Outlook, etc.)"""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
        return {"success": False, "error": "SMTP not configured. Check your .env file."}
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        
        msg.attach(MIMEText(text_body or "Welcome to NOD 2.0", "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        
        return {"success": True, "method": "smtp"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_email_brevo(to_email: str, subject: str, html_body: str, text_body: str = "") -> dict:
    """Send email via Brevo (Sendinblue) API — FREE 300 emails/day"""
    if not BREVO_API_KEY:
        return {"success": False, "error": "BREVO_API_KEY not set"}
    
    try:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        from_email = SMTP_FROM.split("<")[-1].replace(">", "") if "<" in SMTP_FROM else SMTP_FROM
        payload = {
            "sender": {"name": "NOD AI", "email": from_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body or "Welcome to NOD 2.0"
        }
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code in [200, 201, 202]:
            return {"success": True, "method": "brevo", "message_id": r.json().get("messageId", "")}
        return {"success": False, "error": f"Brevo API error: {r.status_code} - {r.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_email_sendgrid(to_email: str, subject: str, html_body: str, text_body: str = "") -> dict:
    """Send email via SendGrid API — FREE 100 emails/day"""
    if not SENDGRID_API_KEY:
        return {"success": False, "error": "SENDGRID_API_KEY not set"}
    
    try:
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        }
        from_email = SMTP_FROM.split("<")[-1].replace(">", "") if "<" in SMTP_FROM else SMTP_FROM
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email, "name": "NOD AI"},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_body or "Welcome to NOD 2.0"},
                {"type": "text/html", "value": html_body}
            ]
        }
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code in [200, 201, 202]:
            return {"success": True, "method": "sendgrid"}
        return {"success": False, "error": f"SendGrid API error: {r.status_code} - {r.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_welcome_email(to_email: str, name: str) -> dict:
    """Send welcome email to new user — tries all providers"""
    html = _get_welcome_template(name)
    text = f"""Hey {name}! Welcome to NOD 2.0 — Your Secure AI Assistant.

Here's what NOD can do for you:
- AI Chat with Ollama (local, private)
- Bank-Level Security (bcrypt, JWT, AES-256 vault)
- Sensitive Data Scanner (PAN, Aadhaar, Bank auto-detect)
- Smart File Manager (sandboxed, safe)
- Voice Commands (coming soon)
- Personal Brain / RAG (coming soon)
- System Integration (coming soon)

Your Security Promise:
NOD will NEVER delete files without double confirmation.
NEVER install software without your explicit "Yes".
NEVER train on your data without permission.
Every action is logged — full transparency.

Start chatting: http://127.0.0.1:5000/chat

© {datetime.now().year} NOD AI. Your Data, Your Control.
"""
    
    subject = "🤖 Welcome to NOD 2.0 — Your Secure AI Assistant"
    
    # Try providers in order: SMTP (Gmail) → Brevo → SendGrid
    for sender in [send_email_smtp, send_email_brevo, send_email_sendgrid]:
        result = sender(to_email, subject, html, text)
        if result["success"]:
            return result
    
    return {"success": False, "error": "All email providers failed. Check your .env configuration."}