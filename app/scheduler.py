from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Глобальный планировщик
scheduler = BackgroundScheduler()

# Флаг для предотвращения одновременного запуска
is_running = False

def get_notification_hours():
    """Получение часов для отправки уведомлений из .env"""
    hours_str = os.getenv("NOTIFICATION_SCHEDULE_HOURS", "9,12,16")
    try:
        return [int(h.strip()) for h in hours_str.split(",")]
    except:
        return [9, 12, 16]


async def send_notifications_async():
    """Асинхронная отправка уведомлений"""
    global is_running
    
    if is_running:
        print("⚠️ Уведомления уже отправляются, пропускаем...")
        return
    
    is_running = True
    
    try:
        print(f"📨 Запуск плановой отправки уведомлений в {datetime.now().strftime('%H:%M:%S')}")
        
        # Импортируем здесь, чтобы избежать циклических импортов
        from app.database import SessionLocal
        from app.routers.notifications import check_deadlines_and_notify
        
        db = SessionLocal()
        try:
            result = await check_deadlines_and_notify(db, None)
            print(f"✅ Отправлено уведомлений: {result}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомлений: {e}")
    finally:
        is_running = False


def send_notifications_sync():
    """Синхронная обертка для асинхронной функции"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(send_notifications_async())
    finally:
        loop.close()


def start_scheduler():
    """Запуск планировщика"""
    # Очищаем существующие задачи
    scheduler.remove_all_jobs()
    
    # Добавляем задачи для каждого часа из расписания
    hours = get_notification_hours()
    for hour in hours:
        scheduler.add_job(
            send_notifications_sync,
            trigger=CronTrigger(hour=hour, minute=0),
            id=f"notification_job_{hour}",
            replace_existing=True
        )
        print(f"⏰ Запланирована отправка уведомлений в {hour:02d}:00")
    
    # Запускаем планировщик
    if not scheduler.running:
        scheduler.start()
        print("🚀 Планировщик уведомлений запущен")


def stop_scheduler():
    """Остановка планировщика"""
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 Планировщик уведомлений остановлен")


def get_next_run_time():
    """Получение времени следующего запуска"""
    jobs = scheduler.get_jobs()
    if jobs:
        next_run = min(job.next_run_time for job in jobs if job.next_run_time)
        return next_run
    return None