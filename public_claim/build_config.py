from __future__ import annotations

from pathlib import Path
import json
import os


REQUIRED_KEYS = (
    "FIREBASE_WEB_API_KEY",
    "FIREBASE_WEB_AUTH_DOMAIN",
    "FIREBASE_WEB_PROJECT_ID",
    "FIREBASE_WEB_STORAGE_BUCKET",
    "FIREBASE_WEB_MESSAGING_SENDER_ID",
    "FIREBASE_WEB_APP_ID",
    "FIREBASE_WEB_MEASUREMENT_ID",
)


def render_config(env: dict[str, str], output_path: Path) -> None:
    missing = [key for key in REQUIRED_KEYS if not env.get(key)]
    if missing:
        raise RuntimeError(
            f"Missing required public-claim configuration: {missing[0]}"
        )

    config = {
        "apiKey": env["FIREBASE_WEB_API_KEY"],
        "authDomain": env["FIREBASE_WEB_AUTH_DOMAIN"],
        "projectId": env["FIREBASE_WEB_PROJECT_ID"],
        "storageBucket": env["FIREBASE_WEB_STORAGE_BUCKET"],
        "messagingSenderId": env["FIREBASE_WEB_MESSAGING_SENDER_ID"],
        "appId": env["FIREBASE_WEB_APP_ID"],
        "measurementId": env["FIREBASE_WEB_MEASUREMENT_ID"],
    }

    template_path = Path(__file__).with_name("config.template.js")
    template = template_path.read_text(encoding="utf-8")
    rendered = template.replace("{{CONFIG_JSON}}", json.dumps(config, indent=2, sort_keys=True))
    output_path.write_text(rendered, encoding="utf-8")


def main() -> None:
    output_path = Path(__file__).with_name("config.js")
    render_config(dict(os.environ), output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
