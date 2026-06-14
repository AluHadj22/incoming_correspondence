import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

# Настройки SMTP из .env
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

async def send_email(
    to_emails: List[str],
    subject: str,
    body: str,
    is_html: bool = False
) -> bool:
    """
    Отправка email через SMTP
    
    Args:
        to_emails: Список email получателей
        subject: Тема письма
        body: Текст письма
        is_html: Является ли тело письма HTML
    
    Returns:
        bool: Успешность отправки
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print("⚠️ SMTP не настроен. Пропускаем отправку email.")
        return False
    
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject
        
        # Добавляем тело письма
        if is_html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))
        
        # Отправляем
        async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
            await smtp.starttls()
            await smtp.login(SMTP_USER, SMTP_PASSWORD)
            await smtp.send_message(msg)
        
        print(f"✅ Email отправлен на {', '.join(to_emails)}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки email: {e}")
        return False

async def send_deadline_notification_email(
    to_email: str,
    correspondence_number: str,
    sender: str,
    deadline: str,
    days_left: int,
    content: str,
    correspondence_id: int
) -> bool:
    """Отправка уведомления о приближении срока исполнения"""
    
    subject = f"⚠️ Напоминание: приближается срок исполнения письма {correspondence_number}"
    
    body = f"""
    Уважаемый сотрудник!
    
    Напоминаем, что у вас есть письмо с приближающимся сроком исполнения:
    
    • Входящий номер: {correspondence_number}
    • Отправитель: {sender}
    • Срок исполнения: {deadline}
    • Осталось дней: {days_left}
    • Содержание: {content}
    
    Пожалуйста, примите необходимые меры.
    
    ---
    Это автоматическое сообщение, пожалуйста, не отвечайте на него.
    """
    
    return await send_email([to_email], subject, body)

async def send_transfer_notification_email(
    to_email: str,
    transferred_by: str,
    correspondence_number: str,
    note: Optional[str] = None
) -> bool:
    """Уведомление о передаче письма"""
    
    subject = f"📨 Вам передано письмо {correspondence_number}"
    
    body = f"""
    Здравствуйте!
    
    Сотрудник {transferred_by} передал(а) вам письмо {correspondence_number} для исполнения.
    
    {"Примечание: " + note if note else ""}
    
    Пожалуйста, войдите в систему для просмотра деталей.
    
    ---
    Это автоматическое сообщение, пожалуйста, не отвечайте на него.
    """
    
    return await send_email([to_email], subject, body)