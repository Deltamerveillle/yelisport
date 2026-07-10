"""Public sport catalogue schemas."""

import uuid

from pydantic import BaseModel, ConfigDict


class SportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    icon_url: str | None
