import httpx
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

# Настройки SMS из .env
SMS_API_URL = os.getenv("SMS_API_URL", "")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")

async def send_sms(phone_number: str, message: str) -> bool:
    """
    Отправка SMS через API (заглушка)
    
    Args:
        phone_number: Номер телефона получателя
        message: Текст сообщения (макс 160 символов)
    
    Returns:
        bool: Успешность отправки
    """
    # Обрезаем сообщение до 160 символов
    if len(message) > 160:
        message = message[:157] + "..."
    
    if not SMS_API_URL or not SMS_API_KEY:
        print(f"⚠️ SMS API не настроен. Пропускаем отправку SMS на {phone_number}")
        print(f"[SMS] Текст: {message}")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            # Пример для SMS.ru
            response = await client.post(
                SMS_API_URL,
                data={
                    "api_id": SMS_API_KEY,
                    "to": phone_number,
                    "msg": message,
                    "json": 1
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "OK":
                    print(f"✅ SMS отправлено на {phone_number}")
                    return True
                else:
                    print(f"❌ Ошибка SMS API: {result}")
                    return False
            else:
                print(f"❌ Ошибка HTTP: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Ошибка отправки SMS: {e}")
        return False

async def send_deadline_notification_sms(
    phone_number: str,
    correspondence_number: str,
    days_left: int,
    deadline: str
) -> bool:
    """Отправка SMS уведомления о приближении срока"""
    
    message = f"Напоминание! Письмо {correspondence_number} требует исполнения до {deadline}. Осталось {days_left} дн."
    
    return await send_sms(phone_number, message)