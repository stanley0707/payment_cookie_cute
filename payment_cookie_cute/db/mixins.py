import datetime
import uuid
from typing import Annotated

from sqlalchemy import (
    DateTime,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

created_timestamp = Annotated[
    datetime.datetime,
    mapped_column(nullable=False, server_default=func.now()),
]


class BaseMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[created_timestamp] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=None,
        onupdate=func.now(),
    )
