from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import logging

from app.database import SessionLocal
from app.routers.notifications import check_deadlines_and_notify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем планировщик
scheduler = BackgroundScheduler()

def run_notification_check():
    """Функция для запуска проверки уведомлений (синхронная обертка)"""
    try:
        # Создаем новую сессию БД
        db = SessionLocal()
        
        # Создаем event loop для async функции
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Запускаем проверку
        result = loop.run_until_complete(
            check_deadlines_and_notify(db, None)
        )
        
        logger.info(f"✅ Плановое уведомление: отправлено {result} уведомлений")
        
        loop.close()
        db.close()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при плановой проверке уведомлений: {e}")

def start_scheduler():
    """Запуск планировщика фоновых задач"""
    
    # Запускаем проверку уведомлений каждый день в 09:00
    scheduler.add_job(
        run_notification_check,
        trigger='cron',
        hour=9,
        minute=0,
        id='daily_notification_check',
        replace_existing=True
    )
    
    # Также запускаем каждые 6 часов для надежности
    scheduler.add_job(
        run_notification_check,
        trigger=IntervalTrigger(hours=6),
        id='interval_notification_check',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("🚀 Планировщик фоновых задач запущен")

def stop_scheduler():
    """Остановка планировщика"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 Планировщик фоновых задач остановлен")