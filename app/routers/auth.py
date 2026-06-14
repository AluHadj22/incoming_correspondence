from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import models, schemas, auth
from app.auth import (
    authenticate_user, create_access_token, get_password_hash,
    get_current_user, create_first_admin
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Настройка шаблонов
templates = Jinja2Templates(directory="app/templates")

# --- HTML страницы ---
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Страница входа"""
    return templates.TemplateResponse(
        "login.html", 
        {"request": request, "error": error}
    )

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: Optional[str] = None):
    """Страница регистрации"""
    return templates.TemplateResponse(
        "register.html", 
        {"request": request, "error": error, "departments": [d.value for d in models.Department]}
    )

@router.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/api/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

# --- API эндпоинты ---
@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Обработка входа в систему"""
    user = authenticate_user(db, username, password)
    if not user:
        error = "Неверное имя пользователя или пароль"
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": error},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    # Создаем токен доступа
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=access_token_expires
    )
    
    # Перенаправляем на дашборд и устанавливаем cookie
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=1800,
        expires=1800
    )
    return response

@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    department: str = Form(...),
    phone_number: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Обработка регистрации нового пользователя"""
    
    # Проверяем совпадение паролей
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Пароли не совпадают", "departments": [d.value for d in models.Department]},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Проверяем, существует ли пользователь с таким username
    existing_user = auth.get_user_by_username(db, username)
    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Пользователь с таким именем уже существует", "departments": [d.value for d in models.Department]},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Проверяем, существует ли пользователь с таким email
    existing_email = auth.get_user_by_email(db, email)
    if existing_email:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Пользователь с таким email уже существует", "departments": [d.value for d in models.Department]},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Проверяем валидность отдела
    try:
        department_enum = models.Department(department)
    except ValueError:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Неверный отдел", "departments": [d.value for d in models.Department]},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Создаем нового пользователя
    hashed_password = get_password_hash(password)
    new_user = models.User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hashed_password,
        department=department_enum,
        is_active=True,
        is_admin=False,
        phone_number=phone_number
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Автоматически входим после регистрации
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.username, "user_id": new_user.id},
        expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=1800,
        expires=1800
    )
    return response

@router.get("/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    """Получение информации о текущем пользователе (API)"""
    return current_user