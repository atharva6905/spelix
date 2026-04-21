"""One-off: copy role from user_metadata to app_metadata for all users.

Run once before deploying L-09 fix. Requires SUPABASE_SERVICE_ROLE_KEY
and SUPABASE_URL env vars.

Usage: uv run python scripts/oneoff/migrate_roles_to_app_metadata.py
"""

import os

import httpx


def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"]
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    resp = httpx.get(
        f"{supabase_url}/auth/v1/admin/users",
        headers=headers,
        params={"per_page": 1000},
        timeout=30.0,
    )
    resp.raise_for_status()
    users = resp.json().get("users", [])

    migrated = 0
    for user in users:
        user_meta = user.get("user_metadata") or {}
        app_meta = user.get("app_metadata") or {}
        role = user_meta.get("role")

        if role and not app_meta.get("role"):
            new_app_meta = {**app_meta, "role": role}
            put_resp = httpx.put(
                f"{supabase_url}/auth/v1/admin/users/{user['id']}",
                headers=headers,
                json={"app_metadata": new_app_meta},
                timeout=30.0,
            )
            put_resp.raise_for_status()
            print(f"Migrated role '{role}' for user {user['id']}")
            migrated += 1

    print(f"\nMigration complete. {migrated} users updated.")


if __name__ == "__main__":
    main()
