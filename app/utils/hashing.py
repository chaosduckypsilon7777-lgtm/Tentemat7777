import hashlib
import json


def stable_hash(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()

