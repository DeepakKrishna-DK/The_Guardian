import os
from .config import get_security_config

class KillSwitchTriggeredError(Exception):
    pass

class KillSwitch:
    def __init__(self):
        self.config = get_security_config()
        self.file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".guardian", "kill_switch")
        
    def is_active(self) -> bool:
        if self.config.kill_switch_active:
            return True
        return os.path.exists(self.file_path)
        
    def activate(self, reason: str):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "w") as f:
            f.write(reason)
            
    def deactivate(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

_kill_switch = KillSwitch()
def get_kill_switch():
    return _kill_switch
