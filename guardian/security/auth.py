import base64
import json
from dataclasses import dataclass
from typing import Optional, Dict, List
from .config import get_security_config

@dataclass
class UserContext:
    user_id: str
    tenant_id: str
    roles: List[str]
    is_authenticated: bool
    is_admin: bool

class AuthLayer:
    def __init__(self):
        self.config = get_security_config()

    def validate_token(self, token: str) -> Optional[Dict]:
        if not token:
            return None
        if self.config.valid_tokens and token in self.config.valid_tokens:
            return {"user_id": "dev_user", "tenant_id": "dev_tenant", "roles": ["admin"]}
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            payload_padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_padded)
            return json.loads(payload_bytes)
        except Exception:
            return None

    def get_user_context(self, user_id: str, token: Optional[str]) -> UserContext:
        if not self.config.auth_required:
            return UserContext(user_id=user_id, tenant_id="default", roles=["user"], is_authenticated=True, is_admin=True)

        payload = self.validate_token(token)
        if not payload:
            return UserContext(user_id=user_id, tenant_id="", roles=[], is_authenticated=False, is_admin=False)
            
        is_admin = "admin" in payload.get("roles", [])
        return UserContext(
            user_id=payload.get("user_id", user_id),
            tenant_id=payload.get("tenant_id", "default"),
            roles=payload.get("roles", ["user"]),
            is_authenticated=True,
            is_admin=is_admin
        )

_auth_layer = AuthLayer()
def get_auth_layer():
    return _auth_layer
