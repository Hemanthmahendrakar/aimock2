"""
Consistent JSON response envelopes used by every route.
"""
from typing import Any

from flask import jsonify


def ok(data: Any = None, status: int = 200):
    body = {"success": True}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def error(code: str, message: str, status: int = 400, details: Any = None):
    body = {"success": False, "error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status
