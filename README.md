# Sasta Dmart Firebase v2 (Pi + Laptop Portal)

This repo now uses **Firebase Realtime Database + Google login** with these deliverables as plain files:

- `pi_checkout_gui_firebase.py` (Pi cart UI + QR login terminal)
- `laptop_firebase_portal.py` (Laptop Flask portal + phone Google sign-in + transactions dashboard)

## Architecture

1. Pi starts checkout and supports:
   - anonymous session, or
   - logged-in session (QR flow)
2. For logged-in session, Pi creates one-time token in Firebase and shows QR.
3. Phone scans QR and opens laptop portal URL (`krato-omen:5000`) on Tailscale.
4. Phone user signs in with Google using Firebase Auth and claims token.
5. Pi detects claimed token and marks session as logged-in.
6. Pi generates bill and writes transaction to Firebase.
7. Laptop portal lists all transactions.

## Pre-filled config

These values are already set in both scripts:

- RTDB URL: `https://sasta-dmart-default-rtdb.asia-southeast1.firebasedatabase.app`
- Laptop base URL: `http://krato-omen:5000`
- Firebase web app config (apiKey/authDomain/projectId/etc)

Service account path defaults to:

`C:\Users\param\Downloads\sasta-dmart-firebase-adminsdk-fbsvc-137566f9a3.json`

You should override it on each machine with env var:

```bash
export FIREBASE_SERVICE_ACCOUNT_PATH="/path/to/your-service-account.json"
```

## Dependencies

No npm/Next.js is required for this version.

### Laptop

```bash
pip install flask firebase-admin
python laptop_firebase_portal.py
```

### Pi

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-tk python3-pil python3-pil.imagetk python3-opencv python3-pyzbar libzbar0
pip install firebase-admin qrcode[pil]
python3 pi_checkout_gui_firebase.py
```

## Firebase checklist

- Authentication -> Sign-in method -> **Google enabled**
- Authentication -> Settings -> **Authorized domains** include hostname used on phone (for you: `krato-omen` if accepted, otherwise use a proper domain)
- Realtime Database rules allow the service account writes/reads

