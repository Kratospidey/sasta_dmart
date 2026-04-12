from __future__ import annotations

from pathlib import Path


def initialize_firebase_admin(service_account_path: str, database_url: str):
    import firebase_admin
    from firebase_admin import credentials

    expanded_path = str(Path(service_account_path).expanduser())
    if not firebase_admin._apps:
        cred = credentials.Certificate(expanded_path)
        firebase_admin.initialize_app(cred, {"databaseURL": database_url})
    return firebase_admin.get_app()
