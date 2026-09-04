"""Validation tests for SMS Connect schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.sms_connect import (
    SMSConnectInterestCreate,
)


def test_valid_sms_connect_interest():
    data = SMSConnectInterestCreate(
        interest_type="recruitment",
        organization_name="Africa Talent FC",
        subject="Recruitment",
        message=(
            "Nous souhaitons discuter d'une "
            "opportunité sportive."
        ),
    )

    assert data.interest_type == "recruitment"


def test_invalid_interest_type_is_rejected():
    with pytest.raises(ValidationError):
        SMSConnectInterestCreate(
            interest_type="spam",
            organization_name="Fake Club",
            subject="Contact",
            message="Un message suffisamment long.",
        )


def test_extra_private_contact_field_is_rejected():
    with pytest.raises(ValidationError):
        SMSConnectInterestCreate(
            interest_type="trial",
            organization_name="SMS Club",
            subject="Essai",
            message="Invitation officielle à un essai.",
            athlete_phone="+2250000000000",
        )


def test_short_message_is_rejected():
    with pytest.raises(ValidationError):
        SMSConnectInterestCreate(
            interest_type="trial",
            organization_name="SMS Club",
            subject="Essai",
            message="Court",
        )
