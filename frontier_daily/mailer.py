"""前沿文献日报 · 邮件发送（可选）
环境变量：EMAIL_ADDRESS / EMAIL_AUTH_CODE / RECIPIENT_EMAIL(可选,缺省用发件人)
可选 SMTP_HOST / SMTP_PORT（默认 smtp.qq.com:465）
任何异常都不抛给调用方，只返回 (是否成功, 说明)。
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
    if not recipients and addr:
        recipients = [addr]
    if not addr or not auth or not recipients:
        return False, "未配置邮件变量，跳过"

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = addr
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html, "html", "utf-8"))

        host = os.environ.get("SMTP_HOST") or "smtp.qq.com"
        port = int(os.environ.get("SMTP_PORT") or "465")
        server = smtplib.SMTP_SSL(host, port, timeout=30)
        server.login(addr, auth)
        server.sendmail(addr, recipients, msg.as_string())
        server.quit()
        return True, "已发送"
    except Exception as e:
        return False, f"发送失败: {e}"