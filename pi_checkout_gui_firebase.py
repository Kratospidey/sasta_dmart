"""
Pi checkout UI with Firebase-backed anonymous/login sessions.

Features:
- Camera preview + barcode scanning.
- Anonymous checkout OR logged-in checkout via QR-based claim flow.
- Pushes transactions directly to Firebase Realtime Database.
- Dark/light mode toggle.
"""

import os
import time
import uuid
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk
from pyzbar.pyzbar import decode

from sasta_dmart.config import load_runtime_config
from sasta_dmart.firebase import initialize_firebase_admin
from sasta_dmart.sessions import (
    DEFAULT_LOGIN_SESSION_TTL_SECONDS,
    build_login_session,
    close_session_record,
    expire_session_record,
)
from sasta_dmart.transactions import (
    build_transaction_payload,
    build_transaction_write_map,
)

try:
    import qrcode
except Exception:  # optional dependency
    qrcode = None

from firebase_admin import db

try:
    from picamera2 import Picamera2
except ImportError as exc:
    raise SystemExit(
        "Picamera2 is not installed. Install it with:\n"
        "sudo apt install -y python3-picamera2"
    ) from exc


try:
    RUNTIME_CONFIG = load_runtime_config("pi")
except RuntimeError as exc:
    raise SystemExit(str(exc)) from exc


# ========= Firebase / network config =========
FIREBASE_DB_URL = RUNTIME_CONFIG.firebase_db_url
SERVICE_ACCOUNT_PATH = RUNTIME_CONFIG.firebase_service_account_path
PUBLIC_CLAIM_BASE_URL = RUNTIME_CONFIG.public_claim_base_url
PI_NODE_NAME = RUNTIME_CONFIG.pi_node_name

# ========= UI / scanner config =========
WINDOW_TITLE = "Sasta Dmart Smart Checkout"
SCAN_COOLDOWN_SECONDS = 1.5
LOGIN_SESSION_TTL_SECONDS = DEFAULT_LOGIN_SESSION_TTL_SECONDS

# Product ID -> Name
PRODUCT_LOOKUP = {
    "00001": "Apple",
    "00002": "Banana",
    "00003": "Orange",
}

THEMES = {
    "dark": {
        "bg": "#191311",
        "panel": "#241a16",
        "card": "#342620",
        "fg": "#fff7ef",
        "subtle": "#ccb2a1",
        "primary": "#d0973f",
        "success": "#57b58b",
        "warn": "#f1c56f",
        "danger": "#cc6b4d",
    },
    "light": {
        "bg": "#f6efe5",
        "panel": "#fff9f2",
        "card": "#f0e4d7",
        "fg": "#2b1c15",
        "subtle": "#7a6256",
        "primary": "#b97a21",
        "success": "#1f7a57",
        "warn": "#e8b95b",
        "danger": "#b9503b",
    },
}


class SelfCheckoutFirebaseApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1280x760")
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        self.theme_name = "dark"

        self.scanning_requested = False
        self.last_scan_time = 0.0
        self.current_frame = None
        self.cart = {}

        self.session_mode = None
        self.login_token = None
        self.logged_in_user = None
        self.poll_job = None
        self.payment_dialog = None
        self.payment_status_var = None
        self.payment_cash_btn = None
        self.payment_card_btn = None
        self.payment_save_in_flight = False

        self._init_firebase()
        self._setup_styles()
        self._build_ui()
        self._setup_camera()

        self.set_status("Choose Anonymous or Login Session to begin checkout.")
        self.update_video_frame()

    def _init_firebase(self):
        initialize_firebase_admin(SERVICE_ACCOUNT_PATH, FIREBASE_DB_URL)

    def _setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self._apply_theme()

    def _apply_theme(self):
        t = THEMES[self.theme_name]
        self.root.configure(bg=t["bg"])
        self.style.configure(
            "Treeview",
            background=t["panel"],
            foreground=t["fg"],
            fieldbackground=t["panel"],
            rowheight=30,
            borderwidth=0,
        )
        self.style.configure("Treeview.Heading", background=t["card"], foreground=t["fg"])

    def _build_ui(self):
        t = THEMES[self.theme_name]
        self.container = tk.Frame(self.root, bg=t["bg"])
        self.container.pack(fill="both", expand=True, padx=16, pady=16)

        self.left = tk.Frame(self.container, bg=t["bg"])
        self.left.pack(side="left", fill="both", expand=True)

        self.right = tk.Frame(self.container, bg=t["bg"], width=420)
        self.right.pack(side="right", fill="y", padx=(16, 0))
        self.right.pack_propagate(False)

        self.header = tk.Frame(self.left, bg=t["bg"])
        self.header.pack(fill="x", pady=(0, 8))

        tk.Label(
            self.header,
            text="Sasta Dmart Checkout",
            font=("Georgia", 22, "bold"),
            bg=t["bg"],
            fg=t["fg"],
        ).pack(side="left")

        tk.Label(
            self.header,
            text="Premium self-checkout kiosk for demo-ready retail flows",
            font=("Segoe UI", 10),
            bg=t["bg"],
            fg=t["subtle"],
        ).pack(side="left", padx=(14, 0), pady=(8, 0))

        self.theme_btn = tk.Button(
            self.header,
            text="Toggle Theme",
            command=self.toggle_theme,
            bg=t["card"],
            fg=t["fg"],
            relief="flat",
            padx=12,
            pady=8,
        )
        self.theme_btn.pack(side="right")

        self.camera_label = tk.Label(self.left, bg="black", relief="flat", bd=0)
        self.camera_label.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Starting...")
        self.status_label = tk.Label(
            self.left,
            textvariable=self.status_var,
            font=("Segoe UI", 11),
            bg=t["bg"],
            fg=t["subtle"],
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(8, 0))

        self._build_right_panel()

    def _build_right_panel(self):
        t = THEMES[self.theme_name]
        for child in self.right.winfo_children():
            child.destroy()

        session_card = tk.Frame(self.right, bg=t["panel"], padx=12, pady=12)
        session_card.pack(fill="x", pady=(0, 12))
        tk.Label(session_card, text="Session", bg=t["panel"], fg=t["fg"], font=("Segoe UI", 15, "bold")).pack(anchor="w")

        tk.Button(session_card, text="Anonymous", command=self.start_anonymous_session, bg=t["warn"], fg="black", relief="flat", pady=8).pack(fill="x", pady=(10, 6))
        tk.Button(session_card, text="Login via Phone", command=self.start_login_session, bg=t["primary"], fg="white", relief="flat", pady=8).pack(fill="x")

        self.session_state_var = tk.StringVar(value="NO SESSION")
        self.session_state_label = tk.Label(
            session_card,
            textvariable=self.session_state_var,
            bg=t["card"],
            fg=t["fg"],
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
        )
        self.session_state_label.pack(anchor="w", pady=(10, 0))

        self.session_info_var = tk.StringVar(value="No session")
        tk.Label(session_card, textvariable=self.session_info_var, bg=t["panel"], fg=t["subtle"], justify="left", wraplength=350).pack(anchor="w", pady=(10, 0))

        self.qr_label = tk.Label(session_card, bg=t["panel"])
        self.qr_label.pack(anchor="center", pady=(10, 0))

        action_card = tk.Frame(self.right, bg=t["panel"], padx=12, pady=12)
        action_card.pack(fill="x", pady=(0, 12))
        tk.Label(action_card, text="Actions", bg=t["panel"], fg=t["fg"], font=("Segoe UI", 15, "bold")).pack(anchor="w")

        tk.Button(action_card, text="Scan Item", command=self.scan_next_item, bg=t["primary"], fg="white", relief="flat", pady=8).pack(fill="x", pady=(10, 6))
        self.generate_bill_btn = tk.Button(
            action_card,
            text="Generate Bill",
            command=self.generate_bill,
            bg=t["success"],
            fg="white",
            relief="flat",
            pady=8,
        )
        self.generate_bill_btn.pack(fill="x", pady=6)
        tk.Button(action_card, text="Clear Cart", command=self.clear_cart, bg=t["warn"], fg="black", relief="flat", pady=8).pack(fill="x", pady=6)
        tk.Button(action_card, text="Exit", command=self.on_exit, bg=t["danger"], fg="white", relief="flat", pady=8).pack(fill="x", pady=6)

        cart_card = tk.Frame(self.right, bg=t["panel"], padx=12, pady=12)
        cart_card.pack(fill="both", expand=True)
        tk.Label(cart_card, text="Cart", bg=t["panel"], fg=t["fg"], font=("Segoe UI", 15, "bold")).pack(anchor="w")

        cart_shell = tk.Frame(cart_card, bg=t["panel"])
        cart_shell.pack(fill="both", expand=True, pady=(10, 0))

        columns = ("name", "qty", "price", "line_total")
        self.cart_tree = ttk.Treeview(cart_shell, columns=columns, show="headings", height=10)
        self.cart_tree.heading("name", text="Item")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("price", text="Unit ₹")
        self.cart_tree.heading("line_total", text="Total ₹")
        self.cart_tree.column("name", width=120, anchor="w")
        self.cart_tree.column("qty", width=45, anchor="center")
        self.cart_tree.column("price", width=80, anchor="e")
        self.cart_tree.column("line_total", width=90, anchor="e")
        self.cart_tree.pack(side="left", fill="both", expand=True)

        cart_scrollbar = ttk.Scrollbar(cart_shell, orient="vertical", command=self.cart_tree.yview)
        cart_scrollbar.pack(side="right", fill="y")
        self.cart_tree.configure(yscrollcommand=cart_scrollbar.set)
        self.cart_tree.bind("<MouseWheel>", self._on_cart_mousewheel)
        self.cart_tree.bind("<Button-4>", self._on_cart_mousewheel_linux)
        self.cart_tree.bind("<Button-5>", self._on_cart_mousewheel_linux)

        self.total_var = tk.StringVar(value="Cart Total: ₹ 0.00")
        tk.Label(cart_card, textvariable=self.total_var, bg=t["panel"], fg=t["fg"], font=("Segoe UI", 13, "bold")).pack(anchor="e", pady=(10, 0))

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self._apply_theme()
        self.container.destroy()
        self._build_ui()
        self.refresh_cart_view()

    def _setup_camera(self):
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(main={"size": (960, 540), "format": "RGB888"})
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(0.4)

    def update_video_frame(self):
        frame = self.picam2.capture_array()
        display_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if self.scanning_requested and time.time() - self.last_scan_time >= SCAN_COOLDOWN_SECONDS:
            decoded = self._decode_barcodes(display_frame)
            if decoded:
                if self._handle_decoded_barcode(decoded[0]):
                    self.scanning_requested = False
                    self.last_scan_time = time.time()

        if self.scanning_requested:
            cv2.putText(display_frame, "Scanning... show one barcode", (18, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 50, 60), 2)

        img = Image.fromarray(display_frame)
        imgtk = ImageTk.PhotoImage(image=img)
        self.camera_label.imgtk = imgtk
        self.camera_label.configure(image=imgtk)
        self.root.after(30, self.update_video_frame)

    def _decode_barcodes(self, frame_rgb):
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        return decode(gray)

    def _on_cart_mousewheel(self, event):
        if event.delta:
            self.cart_tree.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _on_cart_mousewheel_linux(self, event):
        if event.num == 4:
            self.cart_tree.yview_scroll(-1, "units")
        elif event.num == 5:
            self.cart_tree.yview_scroll(1, "units")
        return "break"

    def _handle_decoded_barcode(self, barcode_obj):
        try:
            barcode_data = barcode_obj.data.decode("utf-8")
        except Exception:
            self.set_status("Could not decode barcode bytes.")
            return False

        if not (barcode_data.startswith("27") and len(barcode_data) >= 13):
            self.set_status(f"Unsupported barcode format: {barcode_data}")
            return False

        product_id = barcode_data[2:7]
        price_paise = barcode_data[7:12]
        try:
            unit_price = int(price_paise) / 100.0
        except ValueError:
            self.set_status(f"Invalid price in barcode: {barcode_data}")
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
        self.set_status(f"Added {product_name} - ₹ {unit_price:.2f}")
        return True

    def set_status(self, text):
        self.status_var.set(text)

    def scan_next_item(self):
        if not self.session_mode:
            messagebox.showwarning("Session required", "Start Anonymous or Login Session first.")
            return
        self.scanning_requested = True
        self.set_status("Scanning armed. Show one barcode to the camera.")

    def start_anonymous_session(self):
        self._cleanup_login_poll()
        self.session_mode = "anonymous"
        self.login_token = None
        self.logged_in_user = None
        self.qr_label.configure(image="")
        self.session_state_var.set("ANONYMOUS")
        self.session_info_var.set("Anonymous session active")
        self.set_status("Anonymous session started.")

    def start_login_session(self):
        self._cleanup_login_poll()
        self.session_mode = "login_pending"
        self.logged_in_user = None

        token = uuid.uuid4().hex
        payload = build_login_session(
            token=token,
            pi_node=PI_NODE_NAME,
            public_claim_base_url=PUBLIC_CLAIM_BASE_URL,
            ttl_seconds=LOGIN_SESSION_TTL_SECONDS,
        )
        db.reference(f"login_sessions/{token}").set(payload)
        self.login_token = token

        login_url = payload["claim_url"]
        self.session_state_var.set("LOGIN PENDING")
        self.session_info_var.set(
            "Scan with your phone and finish Google sign-in on the hosted claim page.\n"
            f"Link: {login_url}"
        )
        self._render_qr(login_url)
        self.set_status("Waiting for user to login from phone...")
        self._poll_login_status()

    def _render_qr(self, text):
        if not qrcode:
            self.qr_label.configure(text="Install qrcode package for QR rendering", fg="orange")
            return

        qr_img = qrcode.make(text).resize((210, 210))
        tk_img = ImageTk.PhotoImage(qr_img)
        self.qr_label.qr_tk_img = tk_img
        self.qr_label.configure(image=tk_img)

    def _poll_login_status(self):
        if not self.login_token:
            return

        try:
            session_ref = db.reference(f"login_sessions/{self.login_token}")
            session = session_ref.get() or {}
        except Exception as exc:
            self.session_state_var.set("NETWORK ISSUE")
            self.set_status(f"Could not refresh claim status: {exc}")
            self.poll_job = self.root.after(2000, self._poll_login_status)
            return

        expired_session = expire_session_record(session)
        if expired_session.get("status") == "expired" and session.get("status") == "pending":
            session = expired_session
            try:
                session_ref.update({"status": "expired"})
            except Exception:
                pass

        if session.get("status") == "claimed" and session.get("claimed_by"):
            self.session_mode = "logged_in"
            self.logged_in_user = session["claimed_by"]
            name = self.logged_in_user.get("name") or self.logged_in_user.get("email") or "User"
            self.session_state_var.set("SIGNED IN")
            self.session_info_var.set(f"Logged in: {name}\nEmail: {self.logged_in_user.get('email', '-')}")
            self.set_status("Login successful. You can scan items now.")
            return

        if session.get("status") == "expired":
            self.session_mode = None
            self.login_token = None
            self.session_state_var.set("EXPIRED")
            self.session_info_var.set("Login session expired. Start login again.")
            self.set_status("Login expired.")
            return

        if session.get("status") == "cancelled":
            self.session_mode = None
            self.login_token = None
            self.session_state_var.set("CANCELLED")
            self.session_info_var.set("Login session cancelled. Start login again.")
            self.set_status("Login cancelled.")
            return

        self.poll_job = self.root.after(1500, self._poll_login_status)

    def _cleanup_login_poll(self):
        if self.poll_job:
            self.root.after_cancel(self.poll_job)
            self.poll_job = None

    def refresh_cart_view(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        total = 0.0
        for item in self.cart.values():
            line_total = item["qty"] * item["unit_price"]
            total += line_total
            self.cart_tree.insert("", "end", values=(item["name"], item["qty"], f"{item['unit_price']:.2f}", f"{line_total:.2f}"))

        self.total_var.set(f"Cart Total: ₹ {total:.2f}")

    def clear_cart(self):
        if not self.cart:
            return
        if messagebox.askyesno("Clear Cart", "Remove all items from the cart?"):
            self.cart.clear()
            self.refresh_cart_view()
            self.set_status("Cart cleared.")

    def _current_customer_label(self):
        if not self.logged_in_user:
            return "Anonymous"
        return (
            self.logged_in_user.get("name")
            or self.logged_in_user.get("email")
            or "Signed-in customer"
        )

    def _set_payment_dialog_busy(self, busy: bool, message: str | None = None):
        self.payment_save_in_flight = busy
        button_state = "disabled" if busy else "normal"

        if self.payment_cash_btn:
            self.payment_cash_btn.configure(state=button_state)
        if self.payment_card_btn:
            self.payment_card_btn.configure(state=button_state)
        if message and self.payment_status_var is not None:
            self.payment_status_var.set(message)

    def _destroy_payment_dialog(self, force: bool = False):
        if self.payment_save_in_flight and not force:
            return

        if self.payment_dialog and self.payment_dialog.winfo_exists():
            try:
                self.payment_dialog.grab_release()
            except Exception:
                pass
            self.payment_dialog.destroy()

        self.payment_dialog = None
        self.payment_status_var = None
        self.payment_cash_btn = None
        self.payment_card_btn = None
        self.payment_save_in_flight = False

    def _reset_checkout_state(self):
        self.cart.clear()
        self.refresh_cart_view()
        self.scanning_requested = False
        self.session_mode = None
        self.login_token = None
        self.logged_in_user = None
        self.session_state_var.set("NO SESSION")
        self.session_info_var.set("No session")
        self.qr_label.qr_tk_img = None
        self.qr_label.configure(image="", text="")

    def _close_login_session_after_purchase(self):
        if not self.login_token:
            return

        current_session = db.reference(f"login_sessions/{self.login_token}").get() or {}
        closed_session = close_session_record(current_session)
        db.reference(f"login_sessions/{self.login_token}").update(closed_session)

    def _save_bill_with_payment(self, prepared_payload, payment_type: str):
        if self.payment_save_in_flight:
            return

        persisted_payload = {
            **prepared_payload,
            "payment_type": payment_type,
        }
        self._set_payment_dialog_busy(
            True,
            f"Saving {prepared_payload['bill_id']} as {payment_type.title()}...",
        )

        try:
            transaction_id = db.reference("transactions").push().key
            if not transaction_id:
                raise RuntimeError("Could not allocate transaction id from Firebase.")
            updates = build_transaction_write_map(transaction_id, persisted_payload)
            db.reference("/").update(updates)
        except Exception as exc:
            self.session_state_var.set("SAVE FAILED")
            self.set_status(f"Could not save bill to Firebase: {exc}")
            self._set_payment_dialog_busy(
                False,
                "Save failed. Fix the issue and choose Cash or Card to retry.",
            )
            return

        session_close_error = None
        if self.login_token:
            try:
                self._close_login_session_after_purchase()
            except Exception as exc:
                session_close_error = exc

        self._destroy_payment_dialog(force=True)
        self._reset_checkout_state()
        self.set_status(
            f"Saved transaction {persisted_payload['bill_id']} with {payment_type.title()} payment"
        )

        if session_close_error is not None:
            messagebox.showwarning(
                "Bill saved",
                "Saved in Firebase:\n"
                f"{persisted_payload['bill_id']}\n\n"
                f"Payment: {payment_type.title()}\n"
                f"Session close warning: {session_close_error}",
            )
            return

        messagebox.showinfo(
            "Bill generated",
            "Saved in Firebase:\n"
            f"{persisted_payload['bill_id']}\n\n"
            f"Payment: {payment_type.title()}",
        )

    def _open_payment_dialog(self, prepared_payload):
        if self.payment_dialog and self.payment_dialog.winfo_exists():
            self.payment_dialog.lift()
            self.payment_dialog.focus_force()
            return

        t = THEMES[self.theme_name]
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Payment Type")
        dialog.configure(bg=t["panel"])
        dialog.geometry("380x280")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", self._destroy_payment_dialog)
        dialog.focus_force()

        self.payment_dialog = dialog
        self.payment_status_var = tk.StringVar(
            value="Choose Cash or Card to save this bill."
        )

        tk.Label(
            dialog,
            text="Bill Ready",
            font=("Georgia", 18, "bold"),
            bg=t["panel"],
            fg=t["fg"],
        ).pack(anchor="w", padx=18, pady=(18, 8))

        details = [
            ("Bill ID", prepared_payload["bill_id"]),
            ("Customer", self._current_customer_label()),
            ("Total", f"₹ {prepared_payload['total']:.2f}"),
            ("Items", str(prepared_payload["item_count"])),
        ]
        for label, value in details:
            row = tk.Frame(dialog, bg=t["panel"])
            row.pack(fill="x", padx=18, pady=3)
            tk.Label(
                row,
                text=label,
                font=("Segoe UI", 10, "bold"),
                bg=t["panel"],
                fg=t["subtle"],
            ).pack(side="left")
            tk.Label(
                row,
                text=value,
                font=("Segoe UI", 10),
                bg=t["panel"],
                fg=t["fg"],
            ).pack(side="right")

        tk.Label(
            dialog,
            textvariable=self.payment_status_var,
            bg=t["card"],
            fg=t["fg"],
            justify="left",
            wraplength=320,
            padx=12,
            pady=10,
        ).pack(fill="x", padx=18, pady=(16, 10))

        button_row = tk.Frame(dialog, bg=t["panel"])
        button_row.pack(fill="x", padx=18, pady=(0, 18))

        self.payment_cash_btn = tk.Button(
            button_row,
            text="Cash",
            command=lambda: self._save_bill_with_payment(prepared_payload, "cash"),
            bg=t["warn"],
            fg="black",
            relief="flat",
            padx=14,
            pady=10,
        )
        self.payment_cash_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.payment_card_btn = tk.Button(
            button_row,
            text="Card",
            command=lambda: self._save_bill_with_payment(prepared_payload, "card"),
            bg=t["primary"],
            fg="white",
            relief="flat",
            padx=14,
            pady=10,
        )
        self.payment_card_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))

    def generate_bill(self):
        if not self.session_mode or self.session_mode == "login_pending":
            messagebox.showwarning("Session not ready", "Start an Anonymous session or finish login first.")
            return
        if not self.cart:
            messagebox.showwarning("Empty cart", "Scan at least one item before generating bill.")
            return

        prepared_payload = build_transaction_payload(
            cart_items=list(self.cart.values()),
            session_type="logged_in" if self.session_mode == "logged_in" else "anonymous",
            customer=self.logged_in_user,
            pi_node=PI_NODE_NAME,
        )
        self._open_payment_dialog(prepared_payload)

    def on_exit(self):
        self._cleanup_login_poll()
        try:
            self.picam2.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    SelfCheckoutFirebaseApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
