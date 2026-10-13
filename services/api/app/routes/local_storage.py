"""Short-lived signed download endpoint for files on the local disk."""
from flask import Blueprint, abort, request, send_file
from io import BytesIO

from app.services.file_storage_service import FileStorageService, FileStorageError

bp = Blueprint("local_storage", __name__, url_prefix="/api/v1/storage")


@bp.get("/file")
def get_local_file():
    key = request.args.get("key", "")
    expires = request.args.get("expires", "")
    signature = request.args.get("signature", "")
    if not key or not FileStorageService.verify_signed_url(key, expires, signature):
        abort(403)
    storage = FileStorageService()
    try:
        data = storage.download_bytes(key)
        content_type = storage.get_content_type(key)
    except FileStorageError:
        abort(404)
    return send_file(
        BytesIO(data),
        mimetype=content_type,
        as_attachment=False,
        download_name=key.rsplit("/", 1)[-1],
        max_age=0,
    )
