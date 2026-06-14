from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from app.dependencies import admin_required

from app.database import get_db
from app import models, schemas, auth
from app.dependencies import admin_required
from app.auth import get_password_hash

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

# --- HTML страницы админки ---
@router.get("/", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Главная страница админ-панели"""
    
    # Статистика по пользователям
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.is_active == True).count()
    blocked_users = db.query(models.User).filter(models.User.is_active == False).count()
    admin_count = db.query(models.User).filter(models.User.is_admin == True).count()
    
    # Статистика по отделам
    school_dept_count = db.query(models.User).filter(
        models.User.department == models.Department.SCHOOL_DEPARTMENT
    ).count()
    gia_dept_count = db.query(models.User).filter(
        models.User.department == models.Department.GIA_DEPARTMENT
    ).count()
    departement_count = db.query(models.User).filter(
        models.User.department == models.Department.DEPARTEMENT
    ).count()
    
    # Статистика по письмам
    total_correspondences = db.query(models.Correspondence).count()
    completed_correspondences = db.query(models.Correspondence).filter(
        models.Correspondence.status == models.CorrespondenceStatus.COMPLETED
    ).count()
    pending_correspondences = db.query(models.Correspondence).filter(
        models.Correspondence.status == models.CorrespondenceStatus.PENDING
    ).count()
    
    stats = {
        "total_users": total_users,
        "active_users": active_users,
        "blocked_users": blocked_users,
        "admin_count": admin_count,
        "school_dept_count": school_dept_count,
        "gia_dept_count": gia_dept_count,
        "departement_count": departement_count,
        "total_correspondences": total_correspondences,
        "completed_correspondences": completed_correspondences,
        "pending_correspondences": pending_correspondences
    }
    
    return templates.TemplateResponse(
        "admin_panel.html",
        {
            "request": request,
            "current_user": current_user,
            "stats": stats
        }
    )

@router.get("/users", response_class=HTMLResponse)
async def manage_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required),
    department: Optional[str] = None,
    is_active: Optional[str] = None
):
    """Управление пользователями"""
    
    query = db.query(models.User)
    
    # Фильтр по отделу
    if department:
        try:
            dept_enum = models.Department(department)
            query = query.filter(models.User.department == dept_enum)
        except ValueError:
            pass
    
    # Фильтр по статусу
    if is_active == "active":
        query = query.filter(models.User.is_active == True)
    elif is_active == "blocked":
        query = query.filter(models.User.is_active == False)
    
    users = query.order_by(models.User.created_at.desc()).all()
    
    departments = [d.value for d in models.Department]
    
    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "current_user": current_user,
            "users": users,
            "departments": departments,
            "selected_department": department,
            "selected_status": is_active
        }
    )

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def view_user_details(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Просмотр деталей пользователя"""
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Статистика по письмам пользователя
    assigned_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == user_id
    ).count()
    
    completed_count = db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == user_id,
        models.Correspondence.status == models.CorrespondenceStatus.COMPLETED
    ).count()
    
    created_count = db.query(models.Correspondence).filter(
        models.Correspondence.created_by_id == user_id
    ).count()
    
    # Переданные письма
    transferred_to_count = db.query(models.CorrespondenceTransfer).filter(
        models.CorrespondenceTransfer.transferred_to_id == user_id,
        models.CorrespondenceTransfer.is_active == True
    ).count()
    
    transferred_by_count = db.query(models.CorrespondenceTransfer).filter(
        models.CorrespondenceTransfer.transferred_by_id == user_id
    ).count()
    
    user_stats = {
        "assigned_count": assigned_count,
        "completed_count": completed_count,
        "created_count": created_count,
        "transferred_to_count": transferred_to_count,
        "transferred_by_count": transferred_by_count
    }
    
    return templates.TemplateResponse(
        "admin_user_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "target_user": user,
            "stats": user_stats,
            "departments": [d.value for d in models.Department]
        }
    )

# --- API эндпоинты для администрирования ---
@router.post("/users/{user_id}/block")
async def block_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Блокировка пользователя"""
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    
    return RedirectResponse(
        url="/admin/users",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Разблокировка пользователя"""
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    db.commit()
    
    return RedirectResponse(
        url="/admin/users",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/users/{user_id}/make-admin")
async def make_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Назначить пользователя администратором"""
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_admin = True
    db.commit()
    
    return RedirectResponse(
        url=f"/admin/users/{user_id}",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/users/{user_id}/remove-admin")
async def remove_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Снять права администратора"""
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin rights")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_admin = False
    db.commit()
    
    return RedirectResponse(
        url=f"/admin/users/{user_id}",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/users/{user_id}/delete")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Удаление пользователя (полностью)"""
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Сначала удаляем связанные записи
    # Удаляем передачи, где пользователь фигурирует
    db.query(models.CorrespondenceTransfer).filter(
        (models.CorrespondenceTransfer.transferred_by_id == user_id) |
        (models.CorrespondenceTransfer.transferred_to_id == user_id)
    ).delete()
    
    # Обновляем письма: снимаем исполнителя
    db.query(models.Correspondence).filter(
        models.Correspondence.executor_id == user_id
    ).update({"executor_id": None})
    
    # Обновляем письма: снимаем создателя (ставим админа)
    admin_user = db.query(models.User).filter(models.User.is_admin == True).first()
    if admin_user:
        db.query(models.Correspondence).filter(
            models.Correspondence.created_by_id == user_id
        ).update({"created_by_id": admin_user.id})
    
    # Удаляем уведомления пользователя
    db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    ).delete()
    
    # Удаляем пользователя
    db.delete(user)
    db.commit()
    
    return RedirectResponse(
        url="/admin/users",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/users/create")
async def create_user_by_admin(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    department: str = Form(...),
    phone_number: Optional[str] = Form(None),
    is_admin: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Создание пользователя администратором"""
    
    # Проверяем существование
    existing_user = auth.get_user_by_username(db, username)
    if existing_user:
        return templates.TemplateResponse(
            "admin_user_detail.html",
            {
                "request": request,
                "current_user": current_user,
                "target_user": None,
                "stats": {},
                "departments": [d.value for d in models.Department],
                "error": "Пользователь с таким именем уже существует"
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    existing_email = auth.get_user_by_email(db, email)
    if existing_email:
        return templates.TemplateResponse(
            "admin_user_detail.html",
            {
                "request": request,
                "current_user": current_user,
                "target_user": None,
                "stats": {},
                "departments": [d.value for d in models.Department],
                "error": "Пользователь с таким email уже существует"
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        department_enum = models.Department(department)
    except ValueError:
        department_enum = models.Department.SCHOOL_DEPARTMENT
    
    hashed_password = get_password_hash(password)
    new_user = models.User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        department=department_enum,
        is_active=True,
        is_admin=is_admin,
        phone_number=phone_number
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return RedirectResponse(
        url=f"/admin/users/{new_user.id}",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/users/{user_id}/update")
async def update_user_by_admin(
    request: Request,
    user_id: int,
    email: str = Form(...),
    username: str = Form(...),
    full_name: str = Form(...),
    department: str = Form(...),
    phone_number: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin_required)
):
    """Обновление данных пользователя администратором"""
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверяем уникальность username (если изменяется)
    if user.username != username:
        existing = auth.get_user_by_username(db, username)
        if existing:
            return templates.TemplateResponse(
                "admin_user_detail.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "target_user": user,
                    "stats": {},
                    "departments": [d.value for d in models.Department],
                    "error": "Пользователь с таким именем уже существует"
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    # Проверяем уникальность email
    if user.email != email:
        existing = auth.get_user_by_email(db, email)
        if existing:
            return templates.TemplateResponse(
                "admin_user_detail.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "target_user": user,
                    "stats": {},
                    "departments": [d.value for d in models.Department],
                    "error": "Пользователь с таким email уже существует"
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    try:
        department_enum = models.Department(department)
    except ValueError:
        department_enum = user.department
    
    user.email = email
    user.username = username
    user.full_name = full_name
    user.department = department_enum
    user.phone_number = phone_number
    
    db.commit()
    
    return RedirectResponse(
        url=f"/admin/users/{user_id}",
        status_code=status.HTTP_303_SEE_OTHER
    )