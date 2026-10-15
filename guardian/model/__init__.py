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
from guardian.model.catalog import (
    CandidateModelCatalog,
    HardwareRequirement,
    ModelCandidateEntry,
    ModelDeployment,
    ModelHealthStatus,
    TrustLevel,
    get_candidate_catalog,
)
from guardian.model.registry import get_model, get_registry
from guardian.model.task_router import (
    CollaborationRole,
    IntelligentTaskRouter,
    RoutingDecision,
    TaskType,
    get_task_router,
)

__all__ = [
    "BackendInfo",
    "CandidateModelCatalog",
    "CollaborationRole",
    "HardwareRequirement",
    "IntelligentTaskRouter",
    "Message",
    "ModelCandidateEntry",
    "ModelDeployment",
    "ModelError",
    "ModelHealthStatus",
    "ModelInterface",
    "ModelRequest",
    "ModelRequestError",
    "ModelResponse",
    "ModelUnavailableError",
    "Role",
    "RoutingDecision",
    "TaskType",
    "TokenUsage",
    "TrustLevel",
    "get_candidate_catalog",
    "get_model",
    "get_registry",
    "get_task_router",
]

