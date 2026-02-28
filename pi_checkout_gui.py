"""
pi_checkout_gui.py

Raspberry Pi side GUI:
- Uses Pi Camera (Picamera2) for live preview and barcode scanning
- Keeps a local cart
- Sends final bill to the laptop server over the Tailscale network
"""

import time
import uuid
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import requests
from PIL import Image, ImageTk
from pyzbar.pyzbar import decode

try:
    from picamera2 import Picamera2
except ImportError as exc:
    raise SystemExit(
        "Picamera2 is not installed. Install it with:\n"
        "sudo apt install -y python3-picamera2"
    ) from exc


# =========================
# CONFIG
# =========================
LAPTOP_BILL_ENDPOINT = "http://100.100.100.100:5000/api/bills"  # <-- replace with laptop Tailscale IP
WINDOW_TITLE = "Pi Self Checkout"
SCAN_COOLDOWN_SECONDS = 1.5

# Product ID -> Name
PRODUCT_LOOKUP = {
    "00001": "Apple",
    "00002": "Banana",
    "00003": "Orange",
}


class SelfCheckoutApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1100x650")
        self.root.configure(bg="#f5f5f5")
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        self.scanning_requested = False
        self.last_scan_time = 0.0
        self.current_frame = None
        self.cart = {}  # key -> item dict

        self._build_ui()
        self._setup_camera()

        self.status_var.set("Camera ready. Click 'Scan Item' to add the next barcode.")
        self.update_video_frame()

    def _build_ui(self):
        self.main_frame = tk.Frame(self.root, bg="#f5f5f5")
        self.main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Left: camera preview
        self.left_frame = tk.Frame(self.main_frame, bg="#f5f5f5")
        self.left_frame.pack(side="left", fill="both", expand=True)

        self.camera_title = tk.Label(
            self.left_frame,
            text="Pi Camera Preview",
            font=("Arial", 16, "bold"),
            bg="#f5f5f5",
        )
        self.camera_title.pack(anchor="w", pady=(0, 8))

        self.camera_label = tk.Label(
            self.left_frame,
            bg="black",
            width=800,
            height=500,
            relief="solid",
            bd=1,
        )
        self.camera_label.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Starting...")
        self.status_label = tk.Label(
            self.left_frame,
            textvariable=self.status_var,
            font=("Arial", 11),
            bg="#f5f5f5",
            fg="#333333",
            anchor="w",
            justify="left",
        )
        self.status_label.pack(fill="x", pady=(8, 0))

        # Right: actions + cart
        self.right_frame = tk.Frame(self.main_frame, bg="#f5f5f5", width=350)
        self.right_frame.pack(side="right", fill="y", padx=(12, 0))
        self.right_frame.pack_propagate(False)

        self.actions_title = tk.Label(
            self.right_frame,
            text="Actions",
            font=("Arial", 16, "bold"),
            bg="#f5f5f5",
        )
        self.actions_title.pack(anchor="w", pady=(0, 8))

        self.scan_button = tk.Button(
            self.right_frame,
            text="Scan Item",
            font=("Arial", 12, "bold"),
            bg="#1f7aec",
            fg="white",
            activebackground="#185fb5",
            padx=10,
            pady=10,
            command=self.scan_next_item,
        )
        self.scan_button.pack(fill="x", pady=(0, 8))

        self.bill_button = tk.Button(
            self.right_frame,
            text="Generate Bill",
            font=("Arial", 12, "bold"),
            bg="#22a06b",
            fg="white",
            activebackground="#17734b",
            padx=10,
            pady=10,
            command=self.generate_bill,
        )
        self.bill_button.pack(fill="x", pady=(0, 8))

        self.clear_button = tk.Button(
            self.right_frame,
            text="Clear Cart",
            font=("Arial", 12),
            bg="#f3b33d",
            fg="black",
            padx=10,
            pady=10,
            command=self.clear_cart,
        )
        self.clear_button.pack(fill="x", pady=(0, 8))

        self.exit_button = tk.Button(
            self.right_frame,
            text="Exit",
            font=("Arial", 12),
            bg="#d9534f",
            fg="white",
            activebackground="#ac3d39",
            padx=10,
            pady=10,
            command=self.on_exit,
        )
        self.exit_button.pack(fill="x", pady=(0, 16))

        self.cart_title = tk.Label(
            self.right_frame,
            text="Cart",
            font=("Arial", 16, "bold"),
            bg="#f5f5f5",
        )
        self.cart_title.pack(anchor="w", pady=(0, 8))

        columns = ("name", "qty", "price", "line_total")
        self.cart_tree = ttk.Treeview(self.right_frame, columns=columns, show="headings", height=14)
        self.cart_tree.heading("name", text="Item")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("price", text="Unit ₹")
        self.cart_tree.heading("line_total", text="Total ₹")

        self.cart_tree.column("name", width=120, anchor="w")
        self.cart_tree.column("qty", width=45, anchor="center")
        self.cart_tree.column("price", width=70, anchor="e")
        self.cart_tree.column("line_total", width=75, anchor="e")
        self.cart_tree.pack(fill="both", expand=False)

        self.total_var = tk.StringVar(value="Cart Total: ₹ 0.00")
        self.total_label = tk.Label(
            self.right_frame,
            textvariable=self.total_var,
            font=("Arial", 14, "bold"),
            bg="#f5f5f5",
        )
        self.total_label.pack(anchor="e", pady=(10, 0))

    def _setup_camera(self):
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": (800, 480), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(0.5)

    def update_video_frame(self):
        frame = self.picam2.capture_array()

        # Fix color order for display
        display_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        self.current_frame = display_frame.copy()

        # Decode only when the user has armed the next scan
        if self.scanning_requested and time.time() - self.last_scan_time >= SCAN_COOLDOWN_SECONDS:
            decoded_objects = self._decode_barcodes(display_frame)

            if decoded_objects:
                for obj in decoded_objects:
                    x, y, w, h = obj.rect
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                added = self._handle_decoded_barcode(decoded_objects[0])
                if added:
                    self.scanning_requested = False
                    self.last_scan_time = time.time()

        if self.scanning_requested:
            cv2.putText(
                display_frame,
                "Scanning... show one barcode clearly",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 0, 0),
                2,
            )

        img = Image.fromarray(display_frame)
        imgtk = ImageTk.PhotoImage(image=img)
        self.camera_label.imgtk = imgtk
        self.camera_label.configure(image=imgtk)

        self.root.after(30, self.update_video_frame)

    def _decode_barcodes(self, frame_rgb):
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        return decode(gray)

    def _handle_decoded_barcode(self, barcode_obj):
        try:
            barcode_data = barcode_obj.data.decode("utf-8")
        except Exception:
            self.status_var.set("Could not decode barcode bytes.")
            return False

        # Expected: 27 + 5-digit product_id + 5-digit paise + 1 checksum digit
        if not (barcode_data.startswith("27") and len(barcode_data) >= 13):
            self.status_var.set(f"Unsupported barcode format: {barcode_data}")
            return False

        product_id = barcode_data[2:7]
        price_paise = barcode_data[7:12]

        try:
            unit_price = int(price_paise) / 100.0
        except ValueError:
            self.status_var.set(f"Invalid price in barcode: {barcode_data}")
            return False

        product_name = PRODUCT_LOOKUP.get(product_id, f"Unknown ({product_id})")
        cart_key = f"{product_id}_{price_paise}"

        if cart_key not in self.cart:
            self.cart[cart_key] = {
                "product_id": product_id,
                "name": product_name,
                "qty": 0,
                "unit_price": unit_price,
                "barcode": barcode_data,
            }

        self.cart[cart_key]["qty"] += 1
        self.refresh_cart_view()
        self.status_var.set(f"Added: {product_name} - ₹ {unit_price:.2f}")
        return True

    def refresh_cart_view(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        total = 0.0
        for item in self.cart.values():
            line_total = item["qty"] * item["unit_price"]
            total += line_total
            self.cart_tree.insert(
                "",
                "end",
                values=(
                    item["name"],
                    item["qty"],
                    f"{item['unit_price']:.2f}",
                    f"{line_total:.2f}",
                ),
            )

        self.total_var.set(f"Cart Total: ₹ {total:.2f}")

    def scan_next_item(self):
        self.scanning_requested = True
        self.status_var.set("Scanning armed. Show one barcode to the Pi camera.")

    def clear_cart(self):
        if not self.cart:
            return
        if messagebox.askyesno("Clear Cart", "Remove all items from the cart?"):
            self.cart.clear()
            self.refresh_cart_view()
            self.status_var.set("Cart cleared.")

    def generate_bill(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Scan at least one item before generating the bill.")
            return

        items = []
        total = 0.0

        for item in self.cart.values():
            line_total = item["qty"] * item["unit_price"]
            total += line_total
            items.append(
                {
                    "product_id": item["product_id"],
                    "name": item["name"],
                    "qty": item["qty"],
                    "unit_price": round(item["unit_price"], 2),
                    "line_total": round(line_total, 2),
                    "barcode": item["barcode"],
                }
            )

        payload = {
            "bill_id": f"BILL-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "raspberry_pi",
            "items": items,
            "total": round(total, 2),
        }

        try:
            response = requests.post(LAPTOP_BILL_ENDPOINT, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as exc:
            messagebox.showerror(
                "Send Failed",
                "Could not send bill to laptop.\n\n"
                f"Endpoint: {LAPTOP_BILL_ENDPOINT}\n"
                f"Error: {exc}"
            )
            self.status_var.set("Failed to send bill to laptop.")
            return

        self.status_var.set(f"Bill sent successfully: {payload['bill_id']}")
        messagebox.showinfo(
            "Bill Sent",
            f"Bill sent to laptop successfully.\n\nBill ID: {payload['bill_id']}"
        )

        # Reset for next customer
        self.cart.clear()
        self.refresh_cart_view()

    def on_exit(self):
        try:
            self.picam2.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    app = SelfCheckoutApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
