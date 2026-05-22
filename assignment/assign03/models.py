from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.orm import declarative_base, sessionmaker

DB_URL = "postgresql+psycopg://postgres:pass@127.0.0.1:5432/user_db"

engine = create_engine(DB_URL, echo=True)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    birthday = Column(Date, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "birthday": (
                self.birthday.isoformat() if self.birthday else None
            ),
        }

Session = sessionmaker(bind=engine)


