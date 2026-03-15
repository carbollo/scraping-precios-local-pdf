from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LocalSearch(Base):
    __tablename__ = "local_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    location_query: Mapped[str] = mapped_column(String(255))
    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)
    radius_km: Mapped[float] = mapped_column(Float, default=50.0)
    product_names: Mapped[str] = mapped_column(Text)  # nombres separados por coma
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    price_records: Mapped[List["PriceRecord"]] = relationship(
        back_populates="local_search", cascade="all, delete-orphan"
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(50), default="scraping"
    )  # scraping, api, etc.

    price_records: Mapped[List["PriceRecord"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    price_records: Mapped[List["PriceRecord"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class PriceRecord(Base):
    __tablename__ = "price_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    local_search_id: Mapped[int] = mapped_column(
        ForeignKey("local_searches.id", ondelete="CASCADE")
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE")
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )

    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="EUR")

    establishment_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    establishment_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    establishment_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    local_search: Mapped[LocalSearch] = relationship(back_populates="price_records")
    source: Mapped[Source] = relationship(back_populates="price_records")
    product: Mapped[Product] = relationship(back_populates="price_records")


def init_db(engine) -> None:
    """Crear tablas en la base de datos."""
    Base.metadata.create_all(bind=engine)

