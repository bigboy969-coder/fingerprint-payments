"""
FingerPay POS — Local enrollment client.
Captures fingerprint locally, sends template to the Render backend.

Usage: python pos_enroll.py <MERCHANT_API_KEY>
"""

import base64
import sys
import time

import requests

from app.services.biometrics import (
    SCANS_NEEDED,
    build_template,
    capture_enrollment_features,
    enrollment_features_needed,
)

BASE_URL = "https://fingerprint-payments.onrender.com"


def main(api_key: str):
    # 1. Create enrollment session
    r = requests.post(f"{BASE_URL}/enroll/session", headers={"X-API-Key": api_key}, timeout=30)
    r.raise_for_status()
    data = r.json()
    session_id = data["session_id"]
    enroll_url = f"{BASE_URL}{data['enroll_url']}"

    print(f"\nSession: {session_id}")
    print(f"Customer enroll URL: {enroll_url}")
    print("(Show this URL or QR code to the customer via the kiosk screen)")

    # 2. Wait for customer to fill in form on their phone
    print("\nWaiting for customer to submit form...")
    while True:
        r = requests.get(f"{BASE_URL}/enroll/status/{session_id}", timeout=10)
        status = r.json()["status"]
        if status == "pending_scan":
            print("Form submitted! Proceeding to fingerprint capture.")
            break
        if status == "complete":
            print("Already complete.")
            return
        time.sleep(2)

    # 3. Capture fingerprint scans locally
    feature_blobs = []
    needed = SCANS_NEEDED
    scan_num = 0

    while needed > 0:
        scan_num += 1
        print(f"\nScan {scan_num}/{SCANS_NEEDED} — click the capture window, then place finger.")
        try:
            features = capture_enrollment_features(timeout=20)
            feature_blobs.append(features)
            needed = enrollment_features_needed(feature_blobs)
            print(f"  Captured. {needed} more scan(s) needed.")
        except (TimeoutError, ValueError) as e:
            print(f"  {e} — try again.")

    # 4. Build template
    print("\nBuilding template...")
    template = build_template(feature_blobs)
    print(f"Template: {len(template)} bytes")

    # 5. Send template to backend
    r = requests.post(
        f"{BASE_URL}/enroll/complete/{session_id}",
        json={"template": base64.b64encode(template).decode()},
        timeout=30,
    )
    if r.status_code == 200:
        user = r.json().get("user", {})
        print(f"\nEnrollment complete! User: {user.get('full_name')} ({user.get('email')})")
    else:
        print(f"\nBackend error: {r.status_code} — {r.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pos_enroll.py <MERCHANT_API_KEY>")
        sys.exit(1)
    main(sys.argv[1])
