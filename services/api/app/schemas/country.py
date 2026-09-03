"""SMS Nations country schemas."""

import uuid

from pydantic import BaseModel, ConfigDict


class CountryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    iso2: str
    iso3: str
    name: str
    continent_code: str | None
    is_active: bool
