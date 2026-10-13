"""
Guardian Model Layer
====================
Public API for model access.

Usage:
    from guardian.model import get_model, ModelRequest, Message, Role
    model = get_model()
    response = model.complete(ModelRequest(messages=[Message.user("Hello")]))
"""

from guardian.model.interface import (
    BackendInfo,
    Message,
    ModelError,
    ModelInterface,
    ModelRequest,
    ModelRequestError,
    ModelResponse,
    ModelUnavailableError,
    Role,
    TokenUsage,
)
from guardian.model.registry import get_model, get_registry

__all__ = [
    "BackendInfo",
    "Message",
    "ModelError",
    "ModelInterface",
    "ModelRequest",
    "ModelRequestError",
    "ModelResponse",
    "ModelUnavailableError",
    "Role",
    "TokenUsage",
    "get_model",
    "get_registry",
]
