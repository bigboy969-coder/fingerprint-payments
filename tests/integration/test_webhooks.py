"""
Integration tests for POST /webhooks/stripe.

stripe.Webhook.construct_event is mocked so tests don't need a real
signing secret or valid Stripe signature.
"""

import json
from unittest.mock import MagicMock, patch


def _make_event(event_type: str, data_object: dict, account: str = None) -> MagicMock:
    """Build a fake Stripe event object."""
    event = MagicMock()
    event.__getitem__ = lambda self, k: {
        "type": event_type,
        "data": {"object": data_object},
        "account": account or "",
    }[k]
    event.get = lambda k, default=None: {
        "type": event_type,
        "data": {"object": data_object},
        "account": account or "",
    }.get(k, default)
    return event


def _post_webhook(client, event_type: str, data_object: dict, account: str = None):
    fake_event = _make_event(event_type, data_object, account)
    with (
        patch("app.routes.webhooks.STRIPE_WEBHOOK_SECRET", "whsec_test"),
        patch("app.routes.webhooks.stripe.Webhook.construct_event", return_value=fake_event),
    ):
        return client.post(
            "/webhooks/stripe",
            content=json.dumps({"type": event_type}),
            headers={"stripe-signature": "t=1,v1=fake", "content-type": "application/json"},
        )


class TestWebhookSecurity:
    def test_rejects_missing_webhook_secret(self, client):
        with patch("app.routes.webhooks.STRIPE_WEBHOOK_SECRET", ""):
            res = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "fake"},
            )
        assert res.status_code == 500

    def test_rejects_invalid_signature(self, client):
        with (
            patch("app.routes.webhooks.STRIPE_WEBHOOK_SECRET", "whsec_test"),
            patch(
                "app.routes.webhooks.stripe.Webhook.construct_event",
                side_effect=Exception("SignatureVerificationError"),
            ),
        ):
            res = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "bad"},
            )
        assert res.status_code in (400, 500)


class TestPaymentIntentSucceeded:
    def test_marks_transaction_succeeded(self, client, stripe_stub):
        from app.db import create_pending_transaction

        tx = create_pending_transaction(user_id=1, amount=10.00, merchant="Test", merchant_id=None)
        from app.db import update_transaction_result

        update_transaction_result(tx["id"], "pi_test_success", "pending")

        res = _post_webhook(client, "payment_intent.succeeded", {"id": "pi_test_success"})
        assert res.status_code == 200

        from app.db.connection import _fetchone, _get_conn

        with _get_conn() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT stripe_status FROM transactions WHERE stripe_payment_intent_id = ?",
                ("pi_test_success",),
            )
            row = _fetchone(c)
        assert row["stripe_status"] == "succeeded"

    def test_succeeds_even_if_no_matching_transaction(self, client):
        res = _post_webhook(client, "payment_intent.succeeded", {"id": "pi_unknown"})
        assert res.status_code == 200


class TestPaymentIntentFailed:
    def test_marks_transaction_failed(self, client, stripe_stub):
        from app.db import create_pending_transaction, update_transaction_result

        tx = create_pending_transaction(user_id=1, amount=5.00, merchant="Test", merchant_id=None)
        update_transaction_result(tx["id"], "pi_test_fail", "pending")

        res = _post_webhook(client, "payment_intent.payment_failed", {"id": "pi_test_fail"})
        assert res.status_code == 200

        from app.db.connection import _fetchone, _get_conn

        with _get_conn() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT stripe_status FROM transactions WHERE stripe_payment_intent_id = ?",
                ("pi_test_fail",),
            )
            row = _fetchone(c)
        assert row["stripe_status"] == "failed"


class TestAccountUpdated:
    def test_updates_connect_status_to_active(self, client, stripe_stub):
        from app.db import create_merchant, update_merchant_connect

        m = create_merchant("Biz", "Owner", "webhook@test.com", "hash", "keyhash")
        update_merchant_connect(m["id"], "acct_webhook_test", "pending")

        res = _post_webhook(
            client,
            "account.updated",
            {"id": "acct_webhook_test", "details_submitted": True, "charges_enabled": True},
        )
        assert res.status_code == 200

        from app.db import get_merchant_by_id

        updated = get_merchant_by_id(m["id"])
        assert updated["stripe_connect_status"] == "active"

    def test_sets_pending_when_not_charges_enabled(self, client, stripe_stub):
        from app.db import create_merchant, update_merchant_connect

        m = create_merchant("Biz2", "Owner2", "webhook2@test.com", "hash", "keyhash2")
        update_merchant_connect(m["id"], "acct_incomplete", "active")

        res = _post_webhook(
            client,
            "account.updated",
            {"id": "acct_incomplete", "details_submitted": False, "charges_enabled": False},
        )
        assert res.status_code == 200

        from app.db import get_merchant_by_id

        updated = get_merchant_by_id(m["id"])
        assert updated["stripe_connect_status"] == "pending"


class TestAccountDeauthorized:
    def test_marks_connect_as_deauthorized(self, client, stripe_stub):
        from app.db import create_merchant, update_merchant_connect

        m = create_merchant("Biz3", "Owner3", "webhook3@test.com", "hash", "keyhash3")
        update_merchant_connect(m["id"], "acct_deauth_test", "active")

        res = _post_webhook(
            client,
            "account.application.deauthorized",
            {},
            account="acct_deauth_test",
        )
        assert res.status_code == 200

        from app.db import get_merchant_by_id

        updated = get_merchant_by_id(m["id"])
        assert updated["stripe_connect_status"] == "deauthorized"


class TestChargeRefunded:
    def test_marks_transaction_refunded(self, client, stripe_stub):
        from app.db import create_pending_transaction, update_transaction_result

        tx = create_pending_transaction(user_id=1, amount=20.00, merchant="Test", merchant_id=None)
        update_transaction_result(tx["id"], "pi_test_refund", "succeeded")

        res = _post_webhook(
            client,
            "charge.refunded",
            {"payment_intent": "pi_test_refund", "refunded": True},
        )
        assert res.status_code == 200

        from app.db.connection import _fetchone, _get_conn

        with _get_conn() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT stripe_status FROM transactions WHERE stripe_payment_intent_id = ?",
                ("pi_test_refund",),
            )
            row = _fetchone(c)
        assert row["stripe_status"] == "refunded"


class TestUnhandledEvent:
    def test_returns_200_for_unknown_event(self, client):
        res = _post_webhook(client, "invoice.created", {"id": "in_test"})
        assert res.status_code == 200
