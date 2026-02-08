import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

def send_lead_email(subject: str, body: str) -> None:
    print("EMAIL FUNCTION CALLED")

    msg = MIMEMultipart()
    from_addr = "ElectroMart <no-reply@electromart.local>"
    to_addr = settings.SALES_TO_EMAIL

    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.set_debuglevel(1)  # helpful while testing
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.sendmail("no-reply@electromart.local", to_addr, msg.as_string())
