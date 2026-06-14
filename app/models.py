from sqlalchemy import Column, Integer, String, Date, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, date
import enum
from app.database import Base

# Перечисление для статуса письма
class CorrespondenceStatus(str, enum.Enum):
    PENDING = "В ожидании"
    IN_PROGRESS = "В работе"
    COMPLETED = "Исполнено"
    EXPIRED = "Просрочено"
    TRANSFERRED = "Передано"

# Перечисление для отделов
class Department(str, enum.Enum):
    SCHOOL_DEPARTMENT = "Школьный отдел"
    GIA_DEPARTMENT = "Отдел ГИА"
    DEPARTEMENT = "Департмент"

# Перечисление для типов запросов
class RequestType(str, enum.Enum):
    OWN_PURPOSES = "Для собственных целей"
    MINISTRY_OF_EDUCATION = "Для Министерства просвещения России"

# Модель пользователя
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)  # ФИО
    hashed_password = Column(String, nullable=False)
    department = Column(Enum(Department), nullable=False)  # Отдел пользователя
    is_active = Column(Boolean, default=True)  # Не заблокирован ли пользователь
    is_admin = Column(Boolean, default=False)  # Является ли админом
    phone_number = Column(String, nullable=True)  # Для SMS уведомлений
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    # Письма, где пользователь является исполнителем
    assigned_correspondences = relationship("Correspondence", foreign_keys="Correspondence.executor_id", back_populates="executor")
    # Письма, которые пользователь создал
    created_correspondences = relationship("Correspondence", foreign_keys="Correspondence.created_by_id", back_populates="created_by")
    # Переданные ему письма
    received_transfers = relationship("CorrespondenceTransfer", foreign_keys="CorrespondenceTransfer.transferred_to_id", back_populates="transferred_to")
    # Письма, которые он передал другим
    sent_transfers = relationship("CorrespondenceTransfer", foreign_keys="CorrespondenceTransfer.transferred_by_id", back_populates="transferred_by")

# Модель входящей корреспонденции
class Correspondence(Base):
    __tablename__ = "correspondences"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # № - входящий номер (составной)
    incoming_number = Column(String, nullable=False)  # Например: 642/07-25
    incoming_date = Column(Date, nullable=False)  # Дата регистрации
    received_date = Column(Date, nullable=False)  # Поступило (дата поступления)
    sender = Column(String, nullable=False)  # Отправитель
    content = Column(Text, nullable=False)  # Содержание
    deadline = Column(Date, nullable=False)  # Срок исполнения
    status = Column(Enum(CorrespondenceStatus), default=CorrespondenceStatus.PENDING)  # Статус
    
    # Поток письма (извлекается из incoming_number, например "07-25")
    flow = Column(String, nullable=True, index=True)  # Добавлено поле для потока
    
    # Поля для писем-запросов
    request_type = Column(Enum(RequestType), nullable=True)  # Тип запроса (для отчетности)
    request_note = Column(Text, nullable=True)  # Примечание для отчетности по запросам
    
    # Дополнительные поля из вашей таблицы
    sent_info = Column(String, nullable=True)  # Отправлено (инфо об отправке)
    to_whom = Column(String, nullable=True)  # Кому
    control = Column(String, nullable=True)  # Контроль
    report = Column(String, nullable=True)  # Отчет
    report_date = Column(Date, nullable=True)  # Дата отчета
    
    # Внешние ключи
    executor_id = Column(Integer, ForeignKey("users.id"))  # Исполнитель
    created_by_id = Column(Integer, ForeignKey("users.id"))  # Кто создал запись
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notification_sent = Column(Boolean, default=False)  # Отправлено ли уведомление о приближении срока
    completed_at = Column(DateTime, nullable=True)  # Когда выполнено
    
    # Связи
    executor = relationship("User", foreign_keys=[executor_id], back_populates="assigned_correspondences")
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_correspondences")
    transfers = relationship("CorrespondenceTransfer", back_populates="correspondence")

# Модель для передачи письма другому сотруднику
class CorrespondenceTransfer(Base):
    __tablename__ = "correspondence_transfers"
    
    id = Column(Integer, primary_key=True, index=True)
    correspondence_id = Column(Integer, ForeignKey("correspondences.id"), nullable=False)
    transferred_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Кто передал
    transferred_to_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Кому передал
    transfer_date = Column(DateTime, default=datetime.utcnow)  # Время передачи
    note = Column(Text, nullable=True)  # Примечание
    is_active = Column(Boolean, default=True)  # Актуальна ли передача
    
    # Связи
    correspondence = relationship("Correspondence", back_populates="transfers")
    transferred_by = relationship("User", foreign_keys=[transferred_by_id], back_populates="sent_transfers")
    transferred_to = relationship("User", foreign_keys=[transferred_to_id], back_populates="received_transfers")

# Модель для уведомлений (логирование)
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    correspondence_id = Column(Integer, ForeignKey("correspondences.id"), nullable=True)
    notification_type = Column(String)  # email, sms, browser
    sent_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    message = Column(Text)
    
    # Связи
    user = relationship("User")
    correspondence = relationship("Correspondence")