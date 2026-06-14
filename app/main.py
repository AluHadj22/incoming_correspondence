from fastapi import FastAPI, Depends, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date, timedelta
import os
from app.scheduler import start_scheduler, stop_scheduler

from app.database import engine, get_db, Base
from app import models
from app.routers import auth, correspondences, admin, notifications
from app.auth import get_current_user
from app.routers import auth, correspondences, admin, notifications, flows
from app.routers import auth, correspondences, admin, notifications, flows, requests
# Создание таблиц в базе данных
Base.metadata.create_all(bind=engine)

# Инициализация FastAPI
app = FastAPI(
    title="Система учета входящей корреспонденции",
    description="Платформа для учета входящих писем с уведомлениями",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение статических файлов
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Подключение шаблонов
templates = Jinja2Templates(directory="app/templates")

# Подключение роутеров
app.include_router(auth.router)
app.include_router(correspondences.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(flows.router)
app.include_router(requests.router)

# --- Инициализация первого админа при старте ---
@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения"""
    from app.auth import create_first_admin
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        create_first_admin(db)
    finally:
        db.close()
    
    # Запускаем планировщик уведомлений
    start_scheduler()
    
    print("✅ Система учета входящей корреспонденции запущена")
    print("📧 Администратор по умолчанию: admin / admin123")
    print("🔔 Система уведомлений активна")

@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке приложения"""
    stop_scheduler()
    print("👋 Система остановлена")

# --- Основные страницы ---
@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Главная страница - дашборд"""
    
    # Проверяем авторизацию
    current_user = await get_current_user(request, db)
    
    if current_user is None:
        return RedirectResponse(url="/api/auth/login", status_code=302)
    
    # Фоновая проверка уведомлений
    from app.routers.notifications import check_deadlines_and_notify
    background_tasks.add_task(check_deadlines_and_notify, db, background_tasks)
    
    # Получаем статистику
    from app.dependencies import get_dashboard_stats
    stats = await get_dashboard_stats(request, db)
    
    # Получаем письма с приближающимся сроком (до 5 дней)
    today = date.today()
    near_deadline_date = today + timedelta(days=5)
    
    if current_user.is_admin:
        near_deadline_correspondences = db.query(models.Correspondence).filter(
            models.Correspondence.deadline <= near_deadline_date,
            models.Correspondence.deadline >= today,
            models.Correspondence.status != models.CorrespondenceStatus.COMPLETED
        ).order_by(models.Correspondence.deadline.asc()).limit(10).all()
    else:
        from sqlalchemy import and_
        accessible_ids = set()
        
        executor_ids = [c.id for c in db.query(models.Correspondence).filter(
            models.Correspondence.executor_id == current_user.id
        ).all()]
        accessible_ids.update(executor_ids)
        
        creator_ids = [c.id for c in db.query(models.Correspondence).filter(
            models.Correspondence.created_by_id == current_user.id
        ).all()]
        accessible_ids.update(creator_ids)
        
        transferred_ids = [t.correspondence_id for t in db.query(models.CorrespondenceTransfer).filter(
            and_(
                models.CorrespondenceTransfer.transferred_to_id == current_user.id,
                models.CorrespondenceTransfer.is_active == True
            )
        ).all()]
        accessible_ids.update(transferred_ids)
        
        near_deadline_correspondences = db.query(models.Correspondence).filter(
            models.Correspondence.id.in_(accessible_ids),
            models.Correspondence.deadline <= near_deadline_date,
            models.Correspondence.deadline >= today,
            models.Correspondence.status != models.CorrespondenceStatus.COMPLETED
        ).order_by(models.Correspondence.deadline.asc()).limit(10).all()
    
    if current_user.is_admin:
        recent_correspondences = db.query(models.Correspondence).order_by(
            models.Correspondence.created_at.desc()
        ).limit(5).all()
    else:
        recent_correspondences = db.query(models.Correspondence).filter(
            models.Correspondence.id.in_(accessible_ids)
        ).order_by(models.Correspondence.created_at.desc()).limit(5).all()
    
    unread_notifications_count = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).count()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "stats": stats,
            "near_deadline_correspondences": near_deadline_correspondences,
            "recent_correspondences": recent_correspondences,
            "unread_notifications_count": unread_notifications_count,
            "today": today
        }
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page_redirect(request: Request):
    """Перенаправление на страницу логина"""
    return RedirectResponse(url="/api/auth/login", status_code=302)

@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Страница справки и инструкций"""
    return templates.TemplateResponse("help.html", {"request": request})

# --- Обработчики ошибок ---
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Обработка 404 ошибки"""
    return templates.TemplateResponse(
        "404.html",
        {"request": request},
        status_code=404
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Обработка 500 ошибки"""
    return templates.TemplateResponse(
        "500.html",
        {"request": request, "error": str(exc)},
        status_code=500
    )