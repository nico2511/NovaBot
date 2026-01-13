from sqlalchemy import Column, Integer, String, Float
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True)
    equity = Column(Float, default=0.0)
    tier = Column(String, default="NEBULA")
