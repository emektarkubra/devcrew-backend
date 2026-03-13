from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

# veri tabanıyla bağlantıyı yönetir. bağlantı kopmuşsa ping atar
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


# insert, update, delete, comit, rollback
SessionLocal = sessionmaker(
    autocommit=False, # commit i manuel yaparsın
    autoflush=False, # otomatik db ye yazma yapmıyor
    bind=engine # engine bağlan 
    )

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback() # veritabanı işlemlerini geri almak için
        raise
    finally:
        db.close()