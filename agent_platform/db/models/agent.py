"""Agent database model and agent_tools association table."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_platform.db.base import Base

if TYPE_CHECKING:
    from agent_platform.db.models.tool import Tool

agent_tools = Table(
    "agent_tools",
    Base.metadata,
    Column("agent_id", String, ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    Column("tool_id", String, ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True),
)


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_agents_tenant_id_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tools: Mapped[list[Tool]] = relationship("Tool", secondary=agent_tools, lazy="selectin")
