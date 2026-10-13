import time
import threading
from typing import Optional
from dataclasses import dataclass, field
from guardian.laptop.safety import is_kill_triggered, show_indicator, hide_indicator

@dataclass
class ComputerUseSession:
    """Stage 3 Computer Use Session."""
    
    session_id: str
    action_budget: int = 10
    timeout_seconds: int = 300
    
    _actions_used: int = 0
    _start_time: float = 0.0
    _active: bool = False
    _presence_confirmed: bool = False

    def confirm_presence(self):
        """Explicit, non-reusable confirmation to start the session."""
        self._presence_confirmed = True
        self._start_time = time.time()
        self._active = True
        show_indicator()

    def end_session(self):
        self._active = False
        hide_indicator()

    def is_valid(self) -> bool:
        if not self._active:
            return False
            
        if not self._presence_confirmed:
            return False
            
        if is_kill_triggered():
            self.end_session()
            return False
            
        if self._actions_used >= self.action_budget:
            self.end_session()
            return False
            
        if time.time() - self._start_time > self.timeout_seconds:
            self.end_session()
            return False
            
        return True

    def record_action(self) -> bool:
        """Record an action and return whether it is permitted."""
        if not self.is_valid():
            return False
        self._actions_used += 1
        return True

_ACTIVE_SESSION: Optional[ComputerUseSession] = None

def get_active_session() -> Optional[ComputerUseSession]:
    global _ACTIVE_SESSION
    if _ACTIVE_SESSION and _ACTIVE_SESSION.is_valid():
        return _ACTIVE_SESSION
    return None

def start_session(session_id: str, budget: int = 10) -> ComputerUseSession:
    global _ACTIVE_SESSION
    if _ACTIVE_SESSION:
        _ACTIVE_SESSION.end_session()
    
    _ACTIVE_SESSION = ComputerUseSession(session_id=session_id, action_budget=budget)
    return _ACTIVE_SESSION
