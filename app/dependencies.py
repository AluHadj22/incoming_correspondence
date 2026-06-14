from typing import List, Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date, timedelta

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user, get_current_admin_user, get_current_active_user

# --- Зависимости для работы с пользователями ---
def get_user_repository(db: Session = Depends(get_db)):
    """Получение репозитория пользователей"""
    return db

async def get_current_user_department(request: Request, db: Session = Depends(get_db)):
    """Получение отдела текущего пользователя"""
    current_user = await get_current_active_user(request, db)
    return current_user.department

def check_user_belongs_to_department(
    user_id: int,
    department: models.Department,
    db: Session = Depends(get_db)
):
    """Проверка, принадлежит ли пользователь к отделу"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.department != department:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not belong to {department.value}"
        )
    return user

def get_department_users(
    department: models.Department,
    db: Session
) -> List[models.User]:
    """Получение всех активных пользователей отдела"""
    return db.query(models.User).filter(
        and_(
            models.User.department == department,
            models.User.is_active == True
        )
    ).all()

# --- Зависимости для работы с корреспонденцией ---
def get_correspondence_or_404(
    correspondence_id: int,
    db: Session = Depends(get_db)
) -> models.Correspondence:
    """Получение письма или 404 ошибка"""
    correspondence = db.query(models.Correspondence).filter(
        models.Correspondence.id == correspondence_id
    ).first()
    
    if not correspondence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Correspondence with id {correspondence_id} not found"
        )
    return correspondence

async def check_correspondence_access(
    request: Request,
    correspondence_id: int,
    db: Session = Depends(get_db)
) -> models.Correspondence:
    """Проверка доступа к письму (только исполнитель, создатель или тот, кому передали)"""
    current_user = await get_current_active_user(request, db)
    correspondence = get_correspondence_or_404(correspondence_id, db)
    
    # Админ имеет доступ ко всем письмам
    if current_user.is_admin:
        return correspondence
    
    # Проверяем, является ли пользователь исполнителем
    if correspondence.executor_id == current_user.id:
        return correspondence
    
    # Проверяем, является ли пользователь создателем письма
    if correspondence.created_by_id == current_user.id:
        return correspondence
    
    # Проверяем, передано ли письмо текущему пользователю
    active_transfer = db.query(models.CorrespondenceTransfer).filter(
        and_(
            models.CorrespondenceTransfer.correspondence_id == correspondence.id,
            models.CorrespondenceTransfer.transferred_to_id == current_user.id,
            models.CorrespondenceTransfer.is_active == True
        )
    ).first()
    
    if active_transfer:
        return correspondence
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this correspondence"
    )

async def get_user_correspondences(
    request: Request,
    db: Session = Depends(get_db),
    status_filter: Optional[str] = None,
    days_until_deadline: Optional[int] = None
) -> List[models.Correspondence]:
    """Получение писем пользователя с фильтрацией"""
    current_user = await get_current_active_user(request, db)
    
    query = db.query(models.Correspondence)
    
    # Если не админ - показываем только свои письма
    if not current_user.is_admin:
        query = query.filter(
            or_(
                models.Correspondence.executor_id == current_user.id,
                models.Correspondence.created_by_id == current_user.id,
                models.Correspondence.id.in_(
                    db.query(models.CorrespondenceTransfer.correspondence_id).filter(
                        and_(
                            models.CorrespondenceTransfer.transferred_to_id == current_user.id,
                            models.CorrespondenceTransfer.is_active == True
                        )
                    )
                )
            )
        )
    
    # Фильтр по статусу
    if status_filter:
        query = query.filter(models.Correspondence.status == status_filter)
    
    # Фильтр по количеству дней до дедлайна
    if days_until_deadline is not None:
        target_date = date.today() + timedelta(days=days_until_deadline)
        query = query.filter(models.Correspondence.deadline <= target_date)
        query = query.filter(models.Correspondence.status != models.CorrespondenceStatus.COMPLETED)
    
    return query.order_by(models.Correspondence.deadline.asc()).all()

# --- Зависимости для статистики ---
async def get_dashboard_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Получение статистики для дашборда"""
    current_user = await get_current_active_user(request, db)
    
    # Базовый запрос для писем пользователя
    if current_user.is_admin:
        correspondences = db.query(models.Correspondence).all()
    else:
        # Получаем ID писем, доступных пользователю
        accessible_ids = set()
        
        # Письма, где пользователь исполнитель
        executor_ids = [c.id for c in db.query(models.Correspondence).filter(
            models.Correspondence.executor_id == current_user.id
        ).all()]
        accessible_ids.update(executor_ids)
        
        # Письма, где пользователь создатель
        creator_ids = [c.id for c in db.query(models.Correspondence).filter(
            models.Correspondence.created_by_id == current_user.id
        ).all()]
        accessible_ids.update(creator_ids)
        
        # Письма, переданные пользователю
        transferred_ids = [t.correspondence_id for t in db.query(models.CorrespondenceTransfer).filter(
            and_(
                models.CorrespondenceTransfer.transferred_to_id == current_user.id,
                models.CorrespondenceTransfer.is_active == True
            )
        ).all()]
        accessible_ids.update(transferred_ids)
        
        correspondences = db.query(models.Correspondence).filter(
            models.Correspondence.id.in_(accessible_ids)
        ).all()
    
    today = date.today()
    near_deadline_date = today + timedelta(days=5)
    
    stats = schemas.DashboardStats(
        total_correspondences=len(correspondences),
        pending_count=sum(1 for c in correspondences if c.status == models.CorrespondenceStatus.PENDING),
        in_progress_count=sum(1 for c in correspondences if c.status == models.CorrespondenceStatus.IN_PROGRESS),
        completed_count=sum(1 for c in correspondences if c.status == models.CorrespondenceStatus.COMPLETED),
        expired_count=sum(1 for c in correspondences if c.status == models.CorrespondenceStatus.EXPIRED),
        near_deadline_count=sum(
            1 for c in correspondences 
            if c.deadline <= near_deadline_date 
            and c.deadline >= today
            and c.status != models.CorrespondenceStatus.COMPLETED
        )
    )
    
    return stats

# --- Зависимость для проверки прав админа ---
async def admin_required(
    request: Request,
    db: Session = Depends(get_db)
):
    """Декоратор для проверки прав администратора"""
    current_user = await get_current_admin_user(request, db)
    return current_user