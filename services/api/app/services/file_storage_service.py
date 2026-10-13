"""Persistent local filesystem storage for uploaded project files.

Files are stored under FILE_STORAGE_ROOT, which should be a bind mount to a
folder beside docker-compose.yml on the host. Download links are short-lived
HMAC-signed API URLs so files are never exposed as a public directory.
"""
import hashlib
import hmac
import mimetypes
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

from flask import current_app


class FileStorageError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class FileStorageService:
    def __init__(self):
        self._root = Path(current_app.config["FILE_STORAGE_ROOT"]).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._signed_url_ttl = int(current_app.config["S3_SIGNED_URL_TTL_SECONDS"])

    def _path_for_key(self, key: str) -> Path:
        if not key or key.startswith(("/", "\\")) or "\x00" in key:
            raise FileStorageError("Invalid storage key.")
        path = (self._root / key).resolve()
        if path != self._root and self._root not in path.parents:
            raise FileStorageError("Invalid storage key.")
        return path

    def build_object_key(self, *, prefix: str, filename: str) -> str:
        ext = ""
        if "." in filename:
            candidate = "." + filename.rsplit(".", 1)[-1].lower()
            if len(candidate) <= 12 and candidate[1:].isalnum():
                ext = candidate
        return f"{prefix.strip('/')}/{uuid.uuid4()}{ext}"

    def upload_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
        try:
            path = self._path_for_key(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
            temporary.write_bytes(data)
            os.replace(temporary, path)
            metadata_path = path.with_name(path.name + ".content-type")
            metadata_path.write_text(content_type or "application/octet-stream", encoding="utf-8")
        except (OSError, ValueError) as exc:
            raise FileStorageError(f"Failed to save file to local storage: {exc}") from exc
        return key

    def download_bytes(self, key: str) -> bytes:
        try:
            return self._path_for_key(key).read_bytes()
        except FileNotFoundError as exc:
            raise FileStorageError("Stored file was not found.") from exc
        except (OSError, ValueError) as exc:
            raise FileStorageError(f"Failed to read local file: {exc}") from exc

    def get_content_type(self, key: str) -> str:
        path = self._path_for_key(key)
        metadata_path = path.with_name(path.name + ".content-type")
        try:
            if metadata_path.exists():
                return metadata_path.read_text(encoding="utf-8").strip() or "application/octet-stream"
        except OSError:
            pass
        return mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    def delete_object(self, key: str) -> None:
        if not key:
            return
        try:
            path = self._path_for_key(key)
            path.unlink(missing_ok=True)
            path.with_name(path.name + ".content-type").unlink(missing_ok=True)
            # Remove now-empty parent folders without ever removing the root.
            parent = path.parent
            while parent != self._root and self._root in parent.parents:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        except (OSError, ValueError) as exc:
            raise FileStorageError(f"Failed to delete local file: {exc}") from exc

    def get_signed_url(self, key: str | None) -> str | None:
        if not key:
            return None
        expires = int(time.time()) + self._signed_url_ttl
        message = f"{key}:{expires}".encode("utf-8")
        signature = hmac.new(
            current_app.config["SECRET_KEY"].encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
        return "/api/v1/storage/file?" + urlencode({"key": key, "expires": expires, "signature": signature})

    @staticmethod
    def verify_signed_url(key: str, expires: str, signature: str) -> bool:
        try:
            expiry = int(expires)
        except (TypeError, ValueError):
            return False
        if expiry < int(time.time()) or expiry > int(time.time()) + 86400:
            return False
        message = f"{key}:{expiry}".encode("utf-8")
        expected = hmac.new(
            current_app.config["SECRET_KEY"].encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")
