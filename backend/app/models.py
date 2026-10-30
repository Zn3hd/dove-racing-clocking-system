"""ORM mappings for the initial race management slice (existing SQL schema)."""
from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Loft(Base):
    __tablename__ = "lofts"
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(Text, nullable=False)
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(10, 7), nullable=False)
    verified_at = Column(DateTime(timezone=True))

class Pigeon(Base):
    __tablename__ = "pigeons"
    id = Column(UUID(as_uuid=True), primary_key=True)
    loft_id = Column(UUID(as_uuid=True), ForeignKey("lofts.id"), nullable=False)
    official_ring_number = Column(Text, nullable=False)
    status = Column(Text, nullable=False)

class Race(Base):
    __tablename__ = "races"
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(Text, nullable=False)
    release_latitude = Column(Numeric(10, 7), nullable=False)
    release_longitude = Column(Numeric(10, 7), nullable=False)
    scheduled_release_at = Column(DateTime(timezone=True))
    actual_release_at = Column(DateTime(timezone=True))
    minimum_speed_mpm = Column(Numeric(12, 4), nullable=False)
    display_speed_unit = Column(Text, nullable=False)
    guest_ranking_mode = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True))

class RaceEntry(Base):
    __tablename__ = "race_entries"
    id = Column(UUID(as_uuid=True), primary_key=True)
    race_id = Column(UUID(as_uuid=True), ForeignKey("races.id"), nullable=False)
    pigeon_id = Column(UUID(as_uuid=True), ForeignKey("pigeons.id"), nullable=False)
    loft_id = Column(UUID(as_uuid=True), ForeignKey("lofts.id"), nullable=False)
    loft_latitude = Column(Numeric(10, 7), nullable=False)
    loft_longitude = Column(Numeric(10, 7), nullable=False)
    distance_meters = Column(Numeric(15, 3), nullable=False)
    expected_method = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    registered_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("race_id", "pigeon_id"),)
