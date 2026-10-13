import time
import threading

class CircuitBreaker:
    def __init__(self):
        self.failure_threshold = 5
        self.reset_timeout_seconds = 60
        self.failures = {}
        self.last_failure_time = {}
        self.lock = threading.Lock()
        
    def record_success(self, component: str):
        with self.lock:
            if component in self.failures:
                self.failures[component] = 0
                
    def record_failure(self, component: str, error: str):
        with self.lock:
            self.failures[component] = self.failures.get(component, 0) + 1
            self.last_failure_time[component] = time.time()
            
    def get_state(self, component: str) -> str:
        with self.lock:
            fails = self.failures.get(component, 0)
            if fails >= self.failure_threshold:
                if time.time() - self.last_failure_time.get(component, 0) > self.reset_timeout_seconds:
                    return "HALF_OPEN"
                return "OPEN"
            return "CLOSED"
            
    def is_open(self, component: str) -> bool:
        return self.get_state(component) == "OPEN"

_circuit_breaker = CircuitBreaker()
def get_circuit_breaker():
    return _circuit_breaker
