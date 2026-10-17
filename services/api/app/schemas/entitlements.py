"""Explicit commercial capabilities, independent of consent and legacy premium access."""

from pydantic import BaseModel, ConfigDict


class CommercialEntitlements(BaseModel):
    """Server-configured V1 flags; omission never grants a capability."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    talent_access: bool = False
    enhanced_profile: bool = False
    discover_visibility: bool = False
    connect_access: bool = False
    statistics_insights: bool = False
    priority_visibility: bool = False
