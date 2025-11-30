"""Database models for conversation persistence.

This module defines SQLAlchemy models for storing conversations and messages
using async-compatible patterns with Mapped[] type annotations.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models.

    Includes AsyncAttrs mixin for async relationship loading.
    All models should inherit from this base class.
    """

    pass
