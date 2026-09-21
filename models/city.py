from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from db.base import Base

class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    image_url = Column(String(255), nullable=True)
    video_url = Column(String(255), nullable=True)
    route = Column(String(100), nullable=True)                       # поле по теме №1
    parent_id = Column(Integer, ForeignKey("cities.id"), nullable=True)  # поле по теме №2
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)
