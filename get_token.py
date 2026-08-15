#!/usr/bin/env python3
"""
OpenF1 Token Updater Script

Allows users to quickly obtain a new OAuth2 access token from the OpenF1 API 
using their username (email) and password, and automatically updates the local .env file.
"""

import argparse
import base64
import datetime
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

class OpenF1AuthError(Exception):
    """Exception raised for authentication errors with OpenF1."""
    pass

def decode_jwt_payload(token):
    """
    Decode JWT payload without external dependencies.
    Returns a dictionary of payload claims or empty dict on failure.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        return json.loads(decoded_bytes.decode("utf-8"))
    except Exception:
        return {}

def fetch_openf1_token(username, password, endpoint="https://api.openf1.org/token"):
    """
    Authenticate with OpenF1 API using username and password.
    Returns token string and response payload dictionary.
    """
    params = urllib.parse.urlencode({
        "username": username,
        "password": password
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=params,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PitwallScripts/1.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_body = resp.read().decode("utf-8")
            data = json.loads(raw_body)
            if isinstance(data, dict):
                token = data.get("access_token") or data.get("token")
            elif isinstance(data, str):
                token = data
                data = {"access_token": token}
            else:
                token = None

            if not token:
                raise OpenF1AuthError(f"No access token found in response: {raw_body}")
            return token, data
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            data = json.loads(body)
            detail = data.get("detail", body) if isinstance(data, dict) else body
        except Exception:
            detail = e.reason
        raise OpenF1AuthError(f"Authentication failed (HTTP {e.code}): {detail}")
    except urllib.error.URLError as e:
        raise OpenF1AuthError(f"Failed to connect to OpenF1 authentication service: {e.reason}")

def update_env_file(env_path, updates):
    """
    Updates or appends key-value pairs in updates dictionary into env_path file.
    Preserves existing comments and formatting.
    """
    lines = []
    keys_updated = set()

    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _ = stripped.split("=", 1)
            key = key.strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                keys_updated.add(key)
                continue
        new_lines.append(line)

    # Append any remaining keys that weren't previously in the file
    for key, val in updates.items():
        if key not in keys_updated:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{key}={val}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def main():
    parser = argparse.ArgumentParser(
        description="Authenticate with OpenF1 API and update local .env token."
    )
    parser.add_argument("-u", "--username", type=str, default=None, help="OpenF1 username (email)")
    parser.add_argument("-p", "--password", type=str, default=None, help="OpenF1 password")
    parser.add_argument("-e", "--env-file", type=str, default=".env", help="Path to .env file (default: .env)")
    args = parser.parse_args()

    # Determine username
    username = args.username or os.environ.get("OPENF1_USERNAME")
    if not username:
        username = input("Enter OpenF1 Username/Email: ").strip()

    # Determine password
    password = args.password or os.environ.get("OPENF1_PASSWORD")
    if not password:
        password = getpass.getpass("Enter OpenF1 Password: ")

    if not username or not password:
        print("Error: Username and password are required.", file=sys.stderr)
        sys.exit(1)

    print(f"Requesting new token for '{username}' from OpenF1 API...", file=sys.stderr)
    try:
        token, raw_resp = fetch_openf1_token(username, password)
    except OpenF1AuthError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    # Extract useful information from JWT payload
    payload = decode_jwt_payload(token)
    updates = {
        "OPENF1_TOKEN": token
    }

    issued_at_str = "N/A"
    expires_at_str = "N/A"

    if "iat" in payload:
        try:
            dt_iat = datetime.datetime.fromtimestamp(payload["iat"], tz=datetime.timezone.utc)
            issued_at_str = dt_iat.strftime("%Y-%m-%dT%H:%M:%SZ")
            updates["OPENF1_TOKEN_ISSUED_AT"] = issued_at_str
        except Exception:
            pass

    if "exp" in payload:
        try:
            dt_exp = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc)
            expires_at_str = dt_exp.strftime("%Y-%m-%dT%H:%M:%SZ")
            updates["OPENF1_TOKEN_EXPIRES_AT"] = expires_at_str
        except Exception:
            pass

    email_in_jwt = payload.get("email") or username
    if email_in_jwt:
        updates["OPENF1_USER_EMAIL"] = email_in_jwt

    # Update .env file
    update_env_file(args.env_file, updates)

    print(f"\n[SUCCESS] Token updated in {args.env_file}!", file=sys.stderr)
    print(f"User:       {email_in_jwt}")
    print(f"Issued At:  {issued_at_str}")
    print(f"Expires At: {expires_at_str}")
    if "exp" in payload:
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        remaining_secs = max(0, payload["exp"] - now_ts)
        rem_mins = int(remaining_secs // 60)
        print(f"Valid For:  ~{rem_mins} minutes")

if __name__ == "__main__":
    main()
