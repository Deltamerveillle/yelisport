"""No PSP transport, commercial authority or public event ingestion in rail foundation."""

import uuid

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.schemas.payment_rail import (
    RailInitializationRequest,
    RailInitializationResult,
    RailVerificationResult,
)


@pytest.mark.parametrize(
    "field", ["plan_code", "amount_minor", "currency", "duration_days", "entitlements"]
)
def test_rail_result_cannot_set_commercial_terms(field):
    with pytest.raises(ValidationError):
        RailInitializationResult.model_validate(
            {"external_transaction_id": "psp-1", field: "forged"}
        )
    with pytest.raises(ValidationError):
        RailVerificationResult.model_validate(
            dict(
                external_transaction_id="psp-1",
                payment_reference="SMS-1",
                status="succeeded",
                observed_amount_minor=1234,
                observed_currency="XOF",
            )
            | {field: "forged"}
        )


@pytest.mark.parametrize("value", ["", " ", "bad\x00id", 123, True])
def test_bad_external_id_rejected(value):
    with pytest.raises(ValidationError):
        RailInitializationResult(external_transaction_id=value)


def test_request_is_immutable_and_strict():
    request = RailInitializationRequest(
        idempotency_key=uuid.uuid4(), payment_reference="SMS-1", amount_minor=1234, currency="XOF"
    )
    with pytest.raises(ValidationError):
        request.amount_minor = 1
    with pytest.raises(ValidationError):
        RailInitializationRequest.model_validate(request.model_dump() | {"amount_minor": True})


def test_no_public_trusted_event_ingestion_or_psp_endpoint():
    paths = create_app().openapi()["paths"]
    assert {p for p in paths if "payment" in p or "yeleni" in p or "ecolepay" in p} == {
        "/api/v1/payments/plans",
        "/api/v1/payments/initiate",
        "/api/v1/payments/{transaction_id}",
    }
