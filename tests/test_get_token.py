import base64
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import get_token

class TestGetToken(unittest.TestCase):

    def test_decode_jwt_payload(self):
        # Create dummy JWT with payload: {"sub": "123", "email": "test@example.com", "iat": 1784475507, "exp": 1784479107}
        payload_dict = {
            "sub": "123",
            "email": "test@example.com",
            "iat": 1784475507,
            "exp": 1784479107
        }
        payload_json = json.dumps(payload_dict).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
        jwt = f"header.{payload_b64}.signature"

        decoded = get_token.decode_jwt_payload(jwt)
        self.assertEqual(decoded.get("sub"), "123")
        self.assertEqual(decoded.get("email"), "test@example.com")
        self.assertEqual(decoded.get("iat"), 1784475507)

    def test_update_env_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tmp:
            tmp.write("# Comment header\nOPENF1_TOKEN=old_token_val\nOTHER_KEY=keep_me\n")
            tmp_path = tmp.name

        try:
            updates = {
                "OPENF1_TOKEN": "new_super_token",
                "OPENF1_TOKEN_EXPIRES_AT": "2026-07-20T20:00:00Z"
            }
            get_token.update_env_file(tmp_path, updates)

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("# Comment header", content)
            self.assertIn("OPENF1_TOKEN=new_super_token", content)
            self.assertIn("OTHER_KEY=keep_me", content)
            self.assertIn("OPENF1_TOKEN_EXPIRES_AT=2026-07-20T20:00:00Z", content)
            self.assertNotIn("OPENF1_TOKEN=old_token_val", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @patch("urllib.request.urlopen")
    def test_fetch_openf1_token_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = json.dumps({
            "access_token": "mock_access_token_xyz",
            "token_type": "bearer"
        }).encode("utf-8")
        mock_urlopen.return_value = mock_response

        token, resp_data = get_token.fetch_openf1_token("user@example.com", "secret")
        self.assertEqual(token, "mock_access_token_xyz")
        self.assertEqual(resp_data["token_type"], "bearer")

    @patch("urllib.request.urlopen")
    def test_fetch_openf1_token_failure(self, mock_urlopen):
        import io
        import urllib.error

        body_bytes = json.dumps({"detail": "Incorrect username or password"}).encode("utf-8")
        mock_error = urllib.error.HTTPError(
            url="https://api.openf1.org/token",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(body_bytes)
        )
        mock_urlopen.side_effect = mock_error

        with self.assertRaises(get_token.OpenF1AuthError) as ctx:
            get_token.fetch_openf1_token("wrong@example.com", "wrongpass")

        self.assertIn("Incorrect username or password", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
