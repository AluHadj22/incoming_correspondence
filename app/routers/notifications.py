from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_active_user

load_dotenv()

router = APIRouter(prefix="/notifications", tags=["notifications"])
templates = Jinja2Templates(directory="app/templates")

# Настройки SMTP из .env
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.yandex.ru")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "True").lower() == "true"


# --- Функции для отправки уведомлений ---
async def send_email_notification(user_email: str, subject: str, message: str):
    """Отправка email уведомления через SMTP (Яндекс)"""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("⚠️ SMTP не настроен. Пропускаем отправку email.")
        return False
    
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = user_email
        msg["Subject"] = subject
        
        # Формируем HTML тело письма
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9fafb; padding: 20px; border-radius: 0 0 10px 10px; }}
                .footer {{ text-align: center; padding: 15px; font-size: 12px; color: #666; border-top: 1px solid #e5e7eb; margin-top: 20px; }}
                .deadline {{ color: #e53e3e; font-weight: bold; }}
                .button {{ display: inline-block; padding: 10px 20px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; text-decoration: none; border-radius: 5px; margin-top: 15px; }}
                .message-box {{ background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #667eea; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>📬 Система учета корреспонденции</h2>
                    <p>Автоматическое уведомление</p>
                </div>
                <div class="content">
                    <h3>Уважаемый сотрудник!</h3>
                    <div class="message-box">
                        <p>{message.replace(chr(10), '<br>')}</p>
                    </div>
                    <p style="text-align: center;">
                        <a href="http://localhost:8000/" class="button">Перейти в систему</a>
                    </p>
                </div>
                <div class="footer">
                    <p>Это автоматическое сообщение, пожалуйста, не отвечайте на него.</p>
                    <p>&copy; 2024 Система учета корреспонденции</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, "html"))
        
        # Отправляем через SSL (для Яндекс.почты)
        if SMTP_USE_SSL:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        
        print(f"✅ Email отправлен на {user_email}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки email на {user_email}: {e}")
        return False


async def send_sms_notification(phone_number: str, message: str):
    """Отправка SMS уведомления (заглушка)"""
    print(f"[SMS] To: {phone_number}, Message: {message}")
    return True


async def send_browser_notification(user_id: int, message: str, db: Session):
    """Сохранение уведомления для браузера (в БД)"""
    notification = models.Notification(
        user_id=user_id,
        correspondence_id=None,  # Общее уведомление, не привязанное к конкретному письму
        notification_type="browser",
        message=message,
        is_read=False
    )
    db.add(notification)
    db.commit()
    return True


# --- Основная логика проверки сроков и отправки уведомлений ---
async def check_deadlines_and_notify(db: Session, background_tasks: BackgroundTasks):
    """
    Проверка всех писем на приближение срока и отправка уведомлений.
    Запускается по расписанию или при заходе пользователя.
    """
    today = date.today()
    notification_threshold = today + timedelta(days=5)
    
    # Находим все невыполненные письма, у которых срок <= 5 дней
    pending_correspondences = db.query(models.Correspondence).filter(
        and_(
            models.Correspondence.status != models.CorrespondenceStatus.COMPLETED,
            models.Correspondence.deadline <= notification_threshold,
            models.Correspondence.deadline >= today,
            models.Correspondence.notification_sent == False
        )
    ).all()
    
    notifications_to_send = {}
    
    for corr in pending_correspondences:
        users_to_notify = set()
        
        if corr.executor_id:
            users_to_notify.add(corr.executor_id)
        if corr.created_by_id:
            users_to_notify.add(corr.created_by_id)
        
        transfers = db.query(models.CorrespondenceTransfer).filter(
            and_(
                models.CorrespondenceTransfer.correspondence_id == corr.id,
                models.CorrespondenceTransfer.is_active == True
            )
        ).all()
        
        for transfer in transfers:
            if transfer.transferred_to_id:
                users_to_notify.add(transfer.transferred_to_id)
        
        days_left = (corr.deadline - today).days
        message = f"⚠️ ВНИМАНИЕ! Письмо №{corr.incoming_number} от {corr.sender} требует исполнения.\nСрок: {corr.deadline.strftime('%d.%m.%Y')}\nОсталось дней: {days_left}\nСодержание: {corr.content[:200]}..."
        
        for user_id in users_to_notify:
            if user_id not in notifications_to_send:
                notifications_to_send[user_id] = []
            notifications_to_send[user_id].append({
                "correspondence_id": corr.id,
                "message": message,
                "days_left": days_left,
                "incoming_number": corr.incoming_number,
                "sender": corr.sender,
                "deadline": corr.deadline.strftime('%d.%m.%Y')
            })
        
        corr.notification_sent = True
        db.commit()
    
    for user_id, notifications in notifications_to_send.items():
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            continue
        
        if len(notifications) == 1:
            n = notifications[0]
            full_message = f"Письмо №{n['incoming_number']} от {n['sender']} требует исполнения до {n['deadline']}. Осталось {n['days_left']} дн."
        else:
            full_message = f"📋 У вас {len(notifications)} писем с приближающимся сроком:\n\n"
            for i, n in enumerate(notifications, 1):
                full_message += f"{i}. Письмо №{n['incoming_number']} от {n['sender']} - срок {n['deadline']} (осталось {n['days_left']} дн.)\n"
        
        if user.email:
            background_tasks.add_task(
                send_email_notification,
                user.email,
                f"⚠️ Напоминание: приближается срок исполнения",
                full_message
            )
        
        if user.phone_number:
            background_tasks.add_task(
                send_sms_notification,
                user.phone_number,
                full_message[:160]
            )
        
        await send_browser_notification(user.id, full_message, db)
    
    return len(pending_correspondences)


# --- Эндпоинты для проверки и управления уведомлениями ---
@router.get("/check", response_class=HTMLResponse)
async def check_notifications_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Страница проверки уведомлений (без автоматической отправки)"""
    
    # НЕ отправляем уведомления автоматически при заходе на страницу
    
    # Получаем непрочитанные уведомления текущего пользователя
    unread_notifications = db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == current_user.id,
            models.Notification.is_read == False
        )
    ).order_by(models.Notification.sent_at.desc()).all()
    
    # Получаем письма с приближающимся сроком
    today = date.today()
    near_deadline_date = today + timedelta(days=5)
    
    near_deadline_correspondences = db.query(models.Correspondence).filter(
        and_(
            models.Correspondence.deadline <= near_deadline_date,
            models.Correspondence.deadline >= today,
            models.Correspondence.status != models.CorrespondenceStatus.COMPLETED
        )
    ).all()
    
    # Фильтруем только те, которые доступны пользователю
    accessible_correspondences = []
    for corr in near_deadline_correspondences:
        if current_user.is_admin:
            accessible_correspondences.append(corr)
        elif corr.executor_id == current_user.id or corr.created_by_id == current_user.id:
            accessible_correspondences.append(corr)
        else:
            transfer = db.query(models.CorrespondenceTransfer).filter(
                and_(
                    models.CorrespondenceTransfer.correspondence_id == corr.id,
                    models.CorrespondenceTransfer.transferred_to_id == current_user.id,
                    models.CorrespondenceTransfer.is_active == True
                )
            ).first()
            if transfer:
                accessible_correspondences.append(corr)
    
    # Получаем следующее время отправки
    from app.scheduler import get_next_run_time
    next_run = get_next_run_time()
    next_run_str = next_run.strftime('%d.%m.%Y %H:%M') if next_run else "не запланировано"
    
    return templates.TemplateResponse(
        "notifications_page.html",
        {
            "request": request,
            "current_user": current_user,
            "notified_count": 0,
            "unread_notifications": unread_notifications,
            "near_deadline_correspondences": accessible_correspondences,
            "today": today,
            "next_run": next_run_str
        }
    )


@router.get("/api/unread-count")
async def get_unread_notifications_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """API для получения количества непрочитанных уведомлений"""
    count = db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == current_user.id,
            models.Notification.is_read == False
        )
    ).count()
    return {"unread_count": count}


@router.get("/api/unread")
async def get_unread_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """API для получения непрочитанных уведомлений"""
    notifications = db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == current_user.id,
            models.Notification.is_read == False
        )
    ).order_by(models.Notification.sent_at.desc()).limit(20).all()
    
    return [
        {
            "id": n.id,
            "message": n.message,
            "sent_at": n.sent_at.isoformat(),
            "type": n.notification_type
        }
        for n in notifications
    ]


@router.post("/{notification_id}/mark-read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Отметить уведомление как прочитанное"""
    notification = db.query(models.Notification).filter(
        and_(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id
        )
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    db.commit()
    
    return {"status": "success"}


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Отметить все уведомления как прочитанные"""
    db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == current_user.id,
            models.Notification.is_read == False
        )
    ).update({"is_read": True})
    db.commit()
    
    return {"status": "success"}


@router.post("/trigger-check")
async def trigger_notification_check(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Ручной запуск проверки уведомлений"""
    from app.scheduler import send_notifications_async
    await send_notifications_async()
    return {"status": "success", "message": "Уведомления отправлены"}