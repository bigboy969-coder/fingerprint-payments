# FingerPay POS Terminal Setup Guide

Complete guide to setting up a Windows machine with the fingerprint reader.

---

## Hardware Required

- **Fingerprint Reader**: DigitalPersona U.are.U 4500
  - USB-A connection
  - Manufacturer: HID Global / DigitalPersona
- **Windows PC**: Windows 10 or 11 (64-bit, not S Mode)
  - Tested on: Windows 11 Enterprise

---

## Step 1 — Switch Out of S Mode (if needed)

If your machine came with Windows in S Mode:

1. **Settings → Update & Security → Activation**
2. Click **"Switch out of S Mode"** → Confirm

Free and permanent. Required before installing Python.

---

## Step 2 — Install Python

1. Download Python 3.12 (64-bit) from [python.org/downloads](https://python.org/downloads)
2. Run installer — check **"Add Python to PATH"**
3. Verify:
   ```
   python --version
   ```

---

## Step 3 — Install the DigitalPersona One Touch SDK

Download and install the **DigitalPersona One Touch for Windows SDK**.

After installation verify these files exist:
```
C:\Program Files\DigitalPersona\Bin\COM-ActiveX\DPFPDevX.dll
C:\Program Files\DigitalPersona\Bin\COM-ActiveX\DPFPEngX.dll
C:\Program Files\DigitalPersona\Bin\COM-ActiveX\DPFPShrX.dll
C:\Program Files\DigitalPersona\Bin\COM-ActiveX\DPFPCtlX.dll
C:\Windows\System32\DPFPApi.dll
C:\Windows\System32\dpHFtrEx.dll
C:\Windows\System32\dpHMatch.dll
```

---

## Step 4 — Register the COM DLLs

Open **Terminal as Administrator** and run one at a time:

```powershell
regsvr32 "C:\Program Files\DigitalPersona\Bin\COM-ActiveX\DPFPCtlX.dll"
regsvr32 "C:\Program Files\DigitalPersona\Bin\COM-ActiveX\DPFPDevX.dll"
regsvr32 "C:\Program Files\DigitalPersona\Bin\COM-ActiveX\DPFPEngX.dll"
regsvr32 "C:\Program Files\DigitalPersona\Bin\COM-ActiveX\DPFPShrX.dll"
```

Click **OK** after each success popup.

---

## Step 5 — Verify DpHost Service is Running

```powershell
sc.exe query DpHost
```

Should show `STATE: 4 RUNNING`. If stopped:
```powershell
Start-Service DpHost
```

---

## Step 6 — Plug In the Reader

Plug the U.are.U 4500 into USB. Windows detects it automatically as
"U.are.U 4500 Fingerprint Reader" under **Authentication Devices** in Device Manager.

**Note**: The capture window must be clicked (foreground) for finger events to fire.
This is a DigitalPersona security requirement — `DP_PRIORITY_NORMAL` only
delivers fingerprint data to the active foreground window.

---

## Step 7 — Clone the Project and Install Dependencies

```
git clone https://github.com/bigboy969-coder/fingerprint-payments.git
cd fingerprint-payments
pip install pywin32 requests fastapi uvicorn python-dotenv slowapi passlib pyjwt stripe resend cryptography python-jose[cryptography] bcrypt structlog
```

---

## Step 8 — Test the Reader

```
python test_full_flow.py
```

Click the **FingerPay** window when it appears, place finger 4 times for
enrollment, then once for verification. Should print `MATCH — fingerprint verified!`

---

## Step 9 — Get a Merchant API Key

1. Go to `https://fingerprint-payments.onrender.com`
2. Sign up as a merchant
3. Copy your API key from the dashboard

---

## Running the POS

**Enroll a new customer:**
```
python pos_enroll.py <YOUR_API_KEY>
```

**Charge a customer:**
```
python pos_authenticate.py <YOUR_API_KEY> <AMOUNT>
```

---

## How It Works

```
U.are.U 4500 reader
       ↓  USB
usbdpfp.sys + dpK00701.sys  (Windows kernel drivers)
       ↓  RPC
DpHost.exe  (DigitalPersona Biometric Authentication Service)
       ↓
DPFPApi.dll  (capture)
dpHFtrEx.dll  (feature extraction — 318 bytes per scan)
dpHMatch.dll  (template matching)
       ↓
pos_enroll.py / pos_authenticate.py
       ↓  HTTPS
Render backend  (template storage + Stripe charge)
```

**Enrollment** (one-time):
4 scans → 1632-byte template → AES-256-GCM encrypted → stored in Supabase

**Payment** (every visit):
1 scan → match against stored templates → JWT → Stripe charge

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "No finger detected" | Click the FingerPay window first, hold finger flat for 2-3s |
| "RPC server not listening" | Run `Start-Service DpHost` in admin terminal |
| "Access is denied" on regsvr32 | Open terminal as Administrator |
| Reader not detected | Unplug/replug USB, check Device Manager |
