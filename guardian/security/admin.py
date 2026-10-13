class UnauthorizedError(Exception):
    pass

class AdminControls:
    def require_admin(self, user_context):
        if not user_context or not getattr(user_context, 'is_admin', False):
            raise UnauthorizedError("Admin privileges required")
            
    def disable_tool(self, tool_name: str, admin_context):
        self.require_admin(admin_context)
        
    def get_security_events(self, limit: int = 100) -> list:
        return []
        
    def revoke_session(self, user_id: str, admin_context):
        self.require_admin(admin_context)

_admin_controls = AdminControls()
def get_admin_controls():
    return _admin_controls
