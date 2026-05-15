"""
FingerPay POS — Authentication and payment client.
Captures fingerprint locally via DP SDK, sends the feature blob to the server
for server-side matching, and charges the card on match.

Usage: python pos_authenticate.py <MERCHANT_API_KEY> <AMOUNT>
Example: python pos_authenticate.py mykey123 12.50
"""

import base64
import sys
import time

import requests

from app.services.biometrics import capture_verification_features

BASE_URL = "https://fingerprint-payments.onrender.com"


def main(api_key: str, amount: float):
    headers = {"X-API-Key": api_key}

    # 1. Capture verification feature blob locally via DP SDK
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

    # 2. Send feature blob to server for matching — returns JWT directly on match
    print("Sending to server for matching...")
    r = requests.post(
        f"{BASE_URL}/authenticate",
        json={"features": base64.b64encode(ver_features).decode()},
        headers=headers,
        timeout=15,
    )
    if r.status_code == 401:
        print("Fingerprint not recognised. Payment declined.")
        sys.exit(1)
    if r.status_code != 200:
        print(f"Authentication failed: {r.status_code} — {r.text}")
        sys.exit(1)

    data = r.json()
    token = data["access_token"]
    print(f"  Authenticated: user {data['user_id']}")

    # 3. Charge the card
    print(f"\nCharging ${amount:.2f}...")
    r = requests.post(
        f"{BASE_URL}/pay",
        json={"amount": amount},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )

    if r.status_code == 200:
        result = r.json()
        print("\n Payment approved!")
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
