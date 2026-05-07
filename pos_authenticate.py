"""
FingerPay POS — Authentication and payment client.
Captures fingerprint locally, matches against stored templates, charges card.

Usage: python pos_authenticate.py <MERCHANT_API_KEY> <AMOUNT>
Example: python pos_authenticate.py mykey123 12.50
"""

import base64
import sys
import time

import requests

from app.services.biometrics import TEMPLATE_SIZE, capture_verification_features, verify

BASE_URL = "https://fingerprint-payments.onrender.com"


def main(api_key: str, amount: float):
    headers = {"X-API-Key": api_key}

    # 1. Download all templates from server
    print("Fetching enrolled templates...")
    r = requests.get(f"{BASE_URL}/pos/templates", headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"Failed to fetch templates: {r.status_code} {r.text}")
        sys.exit(1)
    templates = r.json()
    print(f"  {len(templates)} enrolled user(s) found.")

    if not templates:
        print("No enrolled users. Please enroll a customer first.")
        sys.exit(1)

    # 2. Capture verification scan
    print("\nPlace your finger on the reader...")
    print("Starting in 3 seconds...")
    time.sleep(3)
    try:
        ver_features = capture_verification_features(timeout=20)
        print("  Fingerprint captured.")
    except TimeoutError:
        print("No finger detected. Please try again.")
        sys.exit(1)
    except ValueError as e:
        print(f"Poor quality scan: {e}")
        sys.exit(1)

    # 3. Match against all stored templates
    print("Matching...")
    matched_user_id = None
    for entry in templates:
        template = base64.b64decode(entry["template"])
        if len(template) != TEMPLATE_SIZE:
            continue
        if verify(ver_features, template):
            matched_user_id = entry["user_id"]
            break

    if matched_user_id is None:
        print("Fingerprint not recognised. Payment declined.")
        sys.exit(1)

    print(f"  Match found — user {matched_user_id}.")

    # 4. Get JWT from server
    r = requests.post(
        f"{BASE_URL}/pos/identify",
        json={"user_id": matched_user_id},
        headers=headers,
        timeout=15,
    )
    if r.status_code != 200:
        print(f"Identify failed: {r.status_code} {r.text}")
        sys.exit(1)

    data = r.json()
    token = data["access_token"]
    user_name = data["user_name"]
    print(f"  Authenticated: {user_name}")

    # 5. Charge the card
    print(f"\nCharging ${amount:.2f} to {user_name}'s card...")
    r = requests.post(
        f"{BASE_URL}/pay",
        json={"amount": amount},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )

    if r.status_code == 200:
        result = r.json()
        print("\n Payment approved!")
        print(f"  User:   {user_name}")
        print(f"  Amount: ${amount:.2f}")
        print(f"  Status: {result['stripe_status']}")
        print(f"  Tx ID:  {result['transaction']['id']}")
    else:
        print(f"\nPayment failed: {r.status_code} — {r.text}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python pos_authenticate.py <MERCHANT_API_KEY> <AMOUNT>")
        print("Example: python pos_authenticate.py mykey123 12.50")
        sys.exit(1)
    main(sys.argv[1], float(sys.argv[2]))
