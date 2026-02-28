# Self Checkout Demo Baseline

This zip contains:

- `pi_checkout_gui.py` -> Raspberry Pi GUI app
- `laptop_bill_server.py` -> Laptop Flask server that displays bills in a webpage

## Flow

1. Run the laptop server.
2. Open the laptop webpage in a browser.
3. Run the Pi GUI.
4. Click **Scan Item** on the Pi.
5. Show a barcode to the Pi Camera.
6. Click **Generate Bill** on the Pi.
7. The laptop webpage updates with the bill.

---

## 1) Laptop setup

Install dependencies:

```bash
pip install flask
```

Run:

```bash
python laptop_bill_server.py
```

Open in browser on the laptop:

```text
http://127.0.0.1:5000
```

Also find the laptop Tailscale IP:

```bash
tailscale ip -4
```

Copy that IP.

---

## 2) Pi setup

Edit this line inside `pi_checkout_gui.py`:

```python
LAPTOP_BILL_ENDPOINT = "http://100.100.100.100:5000/api/bills"
```

Replace `100.100.100.100` with your laptop's real Tailscale IP.

Install dependencies on the Pi:

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-tk python3-pil python3-pil.imagetk python3-opencv python3-requests python3-pyzbar libzbar0
```

Run:

```bash
python3 pi_checkout_gui.py
```

---

## Barcode format expected

The Pi script expects barcodes in this format:

- `27` -> custom prefix
- next 5 digits -> product ID
- next 5 digits -> price in paise
- final digit -> EAN checksum

Example decoded barcode:

```text
2700001060008
```

Which means:
- product ID = `00001`
- price = `06000` paise = ₹60.00

---

## Notes

- If you want to change product names, edit `PRODUCT_LOOKUP` in `pi_checkout_gui.py`.
- The Pi GUI aggregates duplicate scans by quantity.
- After a successful bill send, the Pi cart is cleared for the next run.
- The laptop server stores received bills in `received_bills.json`.
