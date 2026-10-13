import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional
from .config import get_security_config

@dataclass
class RateLimitResult:
    allowed: bool
    limit_type: Optional[str]
    retry_after_seconds: int

class RateLimiter:
    def __init__(self):
        import os
        self.config = get_security_config()
        self.enabled = os.environ.get("GUARDIAN_RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.max_rpm = self.config.rate_limit_rpm
        self.max_user_rpm = 20
        self.max_concurrent = 5
        self.lock = threading.Lock()
        self.global_requests = deque()
        self.user_requests = {}

    def check(self, user_id: str, ip: Optional[str] = None) -> RateLimitResult:
        if not self.enabled:
            return RateLimitResult(allowed=True, limit_type=None, retry_after_seconds=0)
            
        now = time.time()
        minute_ago = now - 60

        with self.lock:
            while self.global_requests and self.global_requests[0] < minute_ago:
                self.global_requests.popleft()
            
            if user_id not in self.user_requests:
                self.user_requests[user_id] = deque()
            user_reqs = self.user_requests[user_id]
            while user_reqs and user_reqs[0] < minute_ago:
                user_reqs.popleft()

            if len(self.global_requests) >= self.max_rpm:
                return RateLimitResult(allowed=False, limit_type="global_rpm", retry_after_seconds=60)
            if len(user_reqs) >= self.max_user_rpm:
                return RateLimitResult(allowed=False, limit_type="user_rpm", retry_after_seconds=60)

            self.global_requests.append(now)
            user_reqs.append(now)
            return RateLimitResult(allowed=True, limit_type=None, retry_after_seconds=0)

_rate_limiter = RateLimiter()
def get_rate_limiter():
    return _rate_limiter
