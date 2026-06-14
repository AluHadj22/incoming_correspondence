from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

# Перечисления для Pydantic
class DepartmentEnum(str, Enum):
    SCHOOL_DEPARTMENT = "Школьный отдел"
    GIA_DEPARTMENT = "Отдел ГИА"
    DEPARTEMENT = "Департмент"

class CorrespondenceStatusEnum(str, Enum):
    PENDING = "В ожидании"
    IN_PROGRESS = "В работе"
    COMPLETED = "Исполнено"
    EXPIRED = "Просрочено"
    TRANSFERRED = "Передано"

# --- Схемы для пользователей ---
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    department: DepartmentEnum
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[DepartmentEnum] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    username: str
    password: str

# --- Схемы для корреспонденции ---
class CorrespondenceBase(BaseModel):
    incoming_number: str = Field(..., description="Входящий номер, например: 642/07-25")
    incoming_date: date = Field(..., description="Дата входящего документа")
    received_date: date = Field(..., description="Дата поступления")
    sender: str = Field(..., description="Отправитель")
    content: str = Field(..., description="Содержание")
    deadline: date = Field(..., description="Срок исполнения")
    status: CorrespondenceStatusEnum = CorrespondenceStatusEnum.PENDING
    sent_info: Optional[str] = Field(None, description="Отправлено")
    to_whom: Optional[str] = Field(None, description="Кому")
    control: Optional[str] = Field(None, description="Контроль")
    report: Optional[str] = Field(None, description="Отчет")
    report_date: Optional[date] = Field(None, description="Дата отчета")
    executor_id: Optional[int] = Field(None, description="ID исполнителя")

class CorrespondenceCreate(CorrespondenceBase):
    pass

class CorrespondenceUpdate(BaseModel):
    incoming_number: Optional[str] = None
    incoming_date: Optional[date] = None
    received_date: Optional[date] = None
    sender: Optional[str] = None
    content: Optional[str] = None
    deadline: Optional[date] = None
    status: Optional[CorrespondenceStatusEnum] = None
    sent_info: Optional[str] = None
    to_whom: Optional[str] = None
    control: Optional[str] = None
    report: Optional[str] = None
    report_date: Optional[date] = None
    executor_id: Optional[int] = None
    completed_at: Optional[datetime] = None

class CorrespondenceResponse(CorrespondenceBase):
    id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    notification_sent: bool
    completed_at: Optional[datetime] = None
    executor: Optional[UserResponse] = None
    created_by: Optional[UserResponse] = None
    
    model_config = ConfigDict(from_attributes=True)

# --- Схемы для передачи писем ---
class CorrespondenceTransferBase(BaseModel):
    correspondence_id: int
    transferred_to_id: int
    note: Optional[str] = None

class CorrespondenceTransferCreate(CorrespondenceTransferBase):
    pass

class CorrespondenceTransferResponse(CorrespondenceTransferBase):
    id: int
    transferred_by_id: int
    transfer_date: datetime
    is_active: bool
    transferred_by: Optional[UserResponse] = None
    transferred_to: Optional[UserResponse] = None
    correspondence: Optional[CorrespondenceResponse] = None
    
    model_config = ConfigDict(from_attributes=True)

# --- Схемы для уведомлений ---
class NotificationBase(BaseModel):
    user_id: int
    correspondence_id: int
    notification_type: str
    message: str

class NotificationResponse(NotificationBase):
    id: int
    sent_at: datetime
    is_read: bool
    
    model_config = ConfigDict(from_attributes=True)

# --- Схемы для статистики и отчетов ---
class DashboardStats(BaseModel):
    total_correspondences: int
    pending_count: int
    in_progress_count: int
    completed_count: int
    expired_count: int
    near_deadline_count: int  # письма, у которых срок истекает через 5 дней

class UserStatistics(BaseModel):
    user: UserResponse
    assigned_count: int
    completed_count: int
    transferred_count: int

# --- Схемы для токенов ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None