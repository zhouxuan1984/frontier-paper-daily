"""前沿文献日报 · 邮件发送（可选）
环境变量：EMAIL_ADDRESS / EMAIL_AUTH_CODE / RECIPIENT_EMAIL
可选 SMTP_HOST / SMTP_PORT（默认 smtp.qq.com:465）
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(html_path, subject):
    addr = os.environ.get("EMAIL_ADDRESS")
    auth = os.environ.get("EMAIL_AUTH_CODE")
    recipients = os.environ.get("RECIPIENT_EMAIL", "")
    recipients = [r.strip() for r in recipients.split(",") if r.strip()]
    if not addr or not auth or not recipients:
        return False

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = addr
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html, "html", "utf-8"))

    host = os.environ.get("SMTP_HOST", "smtp.qq.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    server = smtplib.SMTP_SSL(host, port, timeout=30)
    server.login(addr, auth)
    server.send_message(msg)
    server.quit()
    return True