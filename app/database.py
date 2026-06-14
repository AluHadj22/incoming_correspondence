from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Создаем директорию для базы данных, если её нет
os.makedirs(os.path.dirname(os.path.abspath("correspondences.db")), exist_ok=True)

# URL для SQLite базы данных
SQLALCHEMY_DATABASE_URL = "sqlite:///./correspondences.db"

# Создаем engine с дополнительными настройками для SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Нужно для SQLite с FastAPI
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()

# Зависимость для получения сессии базы данных
def get_db():
    """
    Генератор для получения сессии базы данных.
    Используется в эндпоинтах FastAPI как зависимость.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()