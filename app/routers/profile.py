from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional, List
from datetime import date, datetime
import os
import shutil
from pathlib import Path

from app.database import get_db
from app import models, schemas, auth
from app.dependencies import get_current_active_user, get_department_users

router = APIRouter(prefix="/profile", tags=["profile"])
templates = Jinja2Templates(directory="app/templates")

# Создаем директорию для аватарок
AVATAR_DIR = Path("app/static/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Страница профиля пользователя"""
    
    # Статистика текущего пользователя
    assigned_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == current_user.id
    ).count()
    
    completed_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == current_user.id,
        models.Correspondence.status == models.CorrespondenceStatus.COMPLETED
    ).count()
    
    created_count = db.query(models.Correspondence).filter(
        models.Correspondence.created_by_id == current_user.id
    ).count()
    
    transferred_to_count = db.query(models.CorrespondenceTransfer).filter(
        models.CorrespondenceTransfer.transferred_to_id == current_user.id,
        models.CorrespondenceTransfer.is_active == True
    ).count()
    
    transferred_by_count = db.query(models.CorrespondenceTransfer).filter(
        models.CorrespondenceTransfer.transferred_by_id == current_user.id
    ).count()
    
    # Просроченные письма
    expired_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == current_user.id,
        models.Correspondence.status == models.CorrespondenceStatus.EXPIRED
    ).count()
    
    # Письма в работе
    in_progress_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == current_user.id,
        models.Correspondence.status == models.CorrespondenceStatus.IN_PROGRESS
    ).count()
    
    user_stats = {
        "assigned_count": assigned_count,
        "completed_count": completed_count,
        "created_count": created_count,
        "transferred_to_count": transferred_to_count,
        "transferred_by_count": transferred_by_count,
        "expired_count": expired_count,
        "in_progress_count": in_progress_count
    }
    
    # Получаем коллег по отделу для сравнения (включая текущего пользователя)
    colleagues = get_department_users(current_user.department, db)
    
    # Статистика коллег (включая текущего пользователя)
    colleagues_stats = []
    for colleague in colleagues:
        # Включаем ВСЕХ сотрудников отдела, включая текущего пользователя
        col_assigned = db.query(models.Correspondence).filter(
            models.Correspondence.executor_id == colleague.id
        ).count()
        
        col_completed = db.query(models.Correspondence).filter(
            models.Correspondence.executor_id == colleague.id,
            models.Correspondence.status == models.CorrespondenceStatus.COMPLETED
        ).count()
        
        col_created = db.query(models.Correspondence).filter(
            models.Correspondence.created_by_id == colleague.id
        ).count()
        
        completion_rate = round((col_completed / col_assigned * 100) if col_assigned > 0 else 0)
        
        colleagues_stats.append({
            "id": colleague.id,
            "full_name": colleague.full_name,
            "assigned_count": col_assigned,
            "completed_count": col_completed,
            "created_count": col_created,
            "completion_rate": completion_rate
        })
    
    # Сортируем коллег по эффективности
    colleagues_stats.sort(key=lambda x: x["completion_rate"], reverse=True)
    
    # Аватар пользователя
    avatar_url = f"/static/avatars/{current_user.id}.png?t={datetime.now().timestamp()}" if (AVATAR_DIR / f"{current_user.id}.png").exists() else None
    
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "current_user": current_user,
            "user_stats": user_stats,
            "colleagues": colleagues_stats,
            "avatar_url": avatar_url,
            "today": date.today(),
            "departments": [d.value for d in models.Department]
        }
    )


@router.get("/{user_id}", response_class=HTMLResponse)
async def public_profile_page(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Публичная страница профиля сотрудника (для просмотра коллегами)"""
    
    # Проверяем, что запрашиваемый пользователь существует
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверяем, что пользователь активен (нельзя смотреть профиль заблокированных)
    if not target_user.is_active:
        raise HTTPException(status_code=403, detail="Профиль недоступен")
    
    # Статистика целевого пользователя
    assigned_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == target_user.id
    ).count()
    
    completed_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == target_user.id,
        models.Correspondence.status == models.CorrespondenceStatus.COMPLETED
    ).count()
    
    created_count = db.query(models.Correspondence).filter(
        models.Correspondence.created_by_id == target_user.id
    ).count()
    
    transferred_to_count = db.query(models.CorrespondenceTransfer).filter(
        models.CorrespondenceTransfer.transferred_to_id == target_user.id,
        models.CorrespondenceTransfer.is_active == True
    ).count()
    
    transferred_by_count = db.query(models.CorrespondenceTransfer).filter(
        models.CorrespondenceTransfer.transferred_by_id == target_user.id
    ).count()
    
    in_progress_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == target_user.id,
        models.Correspondence.status == models.CorrespondenceStatus.IN_PROGRESS
    ).count()
    
    user_stats = {
        "assigned_count": assigned_count,
        "completed_count": completed_count,
        "created_count": created_count,
        "transferred_to_count": transferred_to_count,
        "transferred_by_count": transferred_by_count,
        "in_progress_count": in_progress_count
    }
    
    # Получаем коллег по отделу для сравнения (включая целевого пользователя)
    colleagues = get_department_users(target_user.department, db)
    
    colleagues_stats = []
    for colleague in colleagues:
        col_assigned = db.query(models.Correspondence).filter(
            models.Correspondence.executor_id == colleague.id
        ).count()
        
        col_completed = db.query(models.Correspondence).filter(
            models.Correspondence.executor_id == colleague.id,
            models.Correspondence.status == models.CorrespondenceStatus.COMPLETED
        ).count()
        
        completion_rate = round((col_completed / col_assigned * 100) if col_assigned > 0 else 0)
        
        colleagues_stats.append({
            "id": colleague.id,
            "full_name": colleague.full_name,
            "assigned_count": col_assigned,
            "completed_count": col_completed,
            "completion_rate": completion_rate,
            "is_current": colleague.id == target_user.id
        })
    
    colleagues_stats.sort(key=lambda x: x["completion_rate"], reverse=True)
    
    # Аватар пользователя
    avatar_url = f"/static/avatars/{target_user.id}.png?t={datetime.now().timestamp()}" if (AVATAR_DIR / f"{target_user.id}.png").exists() else None
    
    return templates.TemplateResponse(
        "public_profile.html",
        {
            "request": request,
            "current_user": current_user,
            "target_user": target_user,
            "user_stats": user_stats,
            "colleagues": colleagues_stats,
            "avatar_url": avatar_url,
            "today": date.today()
        }
    )


@router.post("/update")
async def update_profile(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    full_name: str = Form(...),
    phone_number: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Обновление данных профиля"""
    
    # Проверяем уникальность username
    if current_user.username != username:
        existing = db.query(models.User).filter(models.User.username == username).first()
        if existing:
            return templates.TemplateResponse(
                "profile.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "user_stats": {},
                    "colleagues": [],
                    "avatar_url": None,
                    "departments": [d.value for d in models.Department],
                    "error": "Пользователь с таким логином уже существует"
                },
                status_code=400
            )
    
    # Проверяем уникальность email
    if current_user.email != email:
        existing = db.query(models.User).filter(models.User.email == email).first()
        if existing:
            return templates.TemplateResponse(
                "profile.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "user_stats": {},
                    "colleagues": [],
                    "avatar_url": None,
                    "departments": [d.value for d in models.Department],
                    "error": "Пользователь с таким email уже существует"
                },
                status_code=400
            )
    
    current_user.email = email
    current_user.username = username
    current_user.full_name = full_name
    current_user.phone_number = phone_number
    
    db.commit()
    db.refresh(current_user)
    
    return RedirectResponse(url="/profile/", status_code=303)


@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Смена пароля"""
    
    # Проверяем текущий пароль
    if not auth.verify_password(current_password, current_user.hashed_password):
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "current_user": current_user,
                "user_stats": {},
                "colleagues": [],
                "avatar_url": None,
                "departments": [d.value for d in models.Department],
                "password_error": "Текущий пароль введен неверно"
            },
            status_code=400
        )
    
    # Проверяем совпадение нового пароля
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "current_user": current_user,
                "user_stats": {},
                "colleagues": [],
                "avatar_url": None,
                "departments": [d.value for d in models.Department],
                "password_error": "Новый пароль и подтверждение не совпадают"
            },
            status_code=400
        )
    
    # Проверяем длину пароля
    if len(new_password) < 6:
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "current_user": current_user,
                "user_stats": {},
                "colleagues": [],
                "avatar_url": None,
                "departments": [d.value for d in models.Department],
                "password_error": "Пароль должен содержать минимум 6 символов"
            },
            status_code=400
        )
    
    # Меняем пароль
    current_user.hashed_password = auth.get_password_hash(new_password)
    db.commit()
    
    return RedirectResponse(url="/profile/?success=password_changed", status_code=303)


@router.post("/upload-avatar")
async def upload_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Загрузка аватарки"""
    
    # Проверяем тип файла
    if not avatar.content_type.startswith("image/"):
        return JSONResponse(
            status_code=400,
            content={"error": "Можно загружать только изображения"}
        )
    
    # Проверяем размер (не более 2MB)
    contents = await avatar.read()
    if len(contents) > 2 * 1024 * 1024:
        return JSONResponse(
            status_code=400,
            content={"error": "Размер файла не должен превышать 2MB"}
        )
    
    # Сохраняем файл
    file_path = AVATAR_DIR / f"{current_user.id}.png"
    with open(file_path, "wb") as f:
        f.write(contents)
    
    return RedirectResponse(url="/profile/", status_code=303)


@router.post("/delete-avatar")
async def delete_avatar(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Удаление аватарки"""
    
    file_path = AVATAR_DIR / f"{current_user.id}.png"
    if file_path.exists():
        file_path.unlink()
    
    return RedirectResponse(url="/profile/", status_code=303)


@router.get("/colleagues-stats")
async def get_colleagues_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """API для получения статистики коллег (для графиков)"""
    
    colleagues = get_department_users(current_user.department, db)
    
    stats = []
    for colleague in colleagues:
        assigned = db.query(models.Correspondence).filter(
            models.Correspondence.executor_id == colleague.id
        ).count()
        
        completed = db.query(models.Correspondence).filter(
            models.Correspondence.executor_id == colleague.id,
            models.Correspondence.status == models.CorrespondenceStatus.COMPLETED
        ).count()
        
        completion_rate = round((completed / assigned * 100) if assigned > 0 else 0)
        
        stats.append({
            "id": colleague.id,
            "full_name": colleague.full_name,
            "assigned": assigned,
            "completed": completed,
            "completion_rate": completion_rate,
            "is_current": colleague.id == current_user.id
        })
    
    stats.sort(key=lambda x: x["completion_rate"], reverse=True)
    
    return JSONResponse(content=stats)