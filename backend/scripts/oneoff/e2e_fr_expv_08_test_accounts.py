"""Create 3 E2E test accounts for FR-EXPV-08 walkthrough.

Uses Supabase admin API (service role) to:
  - Create 3 accounts: e2e-regular@spelix.internal, e2e-expert@spelix.internal, e2e-admin2@spelix.internal
  - Confirm emails (skip verify)
  - Set app_metadata.role: null (regular), expert_reviewer, admin+biomechanics_qualified
  - Print credentials

Reads creds from the file path in $CREDS_FILE env var.

Run once; re-runs fail with "User already registered" which is fine.
"""

from __future__ import annotations

import json
import os
import secrets
import string
import sys
from urllib import request
from urllib.error import HTTPError

TEST_ACCOUNTS = [
    ("e2e-regular@spelix.internal", None, None),
    ("e2e-expert@spelix.internal", "expert_reviewer", None),
    ("e2e-admin2@spelix.internal", "admin", True),
]


def load_creds(path: str) -> tuple[str, str]:
    url = ""
    key = ""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("SUPABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not url or not key:
        raise RuntimeError("Creds file missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return url, key


def gen_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(20))


def admin_post(url: str, key: str, path: str, body: dict) -> dict:
    req = request.Request(
        f"{url}{path}",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body_text = e.read().decode("utf-8")
        raise RuntimeError(f"HTTP {e.code} on {path}: {body_text}") from e


def create_user(url: str, key: str, email: str, password: str, role: str | None, biomechanics: bool | None) -> dict:
    app_metadata: dict = {}
    if role is not None:
        app_metadata["role"] = role
    if biomechanics is not None:
        app_metadata["biomechanics_qualified"] = biomechanics
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "app_metadata": app_metadata,
    }
    return admin_post(url, key, "/auth/v1/admin/users", payload)


def main() -> int:
    creds_file = os.environ.get("CREDS_FILE", "/tmp/spelix_creds.env")
    url, key = load_creds(creds_file)

    results: list[tuple[str, str, str]] = []
    for email, role, biomechanics in TEST_ACCOUNTS:
        password = gen_password()
        try:
            user = create_user(url, key, email, password, role, biomechanics)
            results.append((email, password, f"created id={user.get('id','?')[:8]} role={role or 'regular'}"))
        except RuntimeError as e:
            if "already been registered" in str(e) or "already registered" in str(e):
                results.append((email, "<existing — reset via admin API if needed>", "already exists, skipping"))
            else:
                print(f"ERROR creating {email}: {e}", file=sys.stderr)
                return 1

    print("=== Test accounts ===")
    for email, password, status in results:
        print(f"{email}")
        print(f"  password: {password}")
        print(f"  {status}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
