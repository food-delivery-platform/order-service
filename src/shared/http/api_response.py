"""HTTP response helpers for API Gateway Lambda proxy integration."""
import json

from src.shared.errors.app_error import AppError

def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }

def ok(data: dict, status_code: int = 200) -> dict:
    return _response(status_code, data)

def error(status_code: int, code: str, message: str) -> dict:
    return _response(status_code, {"error": code, "message": message})

def from_app_error(err: AppError) -> dict:
    return error(err.status_code, err.code, err.message)
