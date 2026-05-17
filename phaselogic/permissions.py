from dataclasses import dataclass, field
from enum import Enum


class Permission(str, Enum):
    READ_ONLY = "read_only"
    GENERATED_WRITE = "generated_write"
    FULL_PROJECT = "full_project"
    NETWORK = "network"
    GIT = "git"
    CLOUD = "cloud"
    DEPLOY = "deploy"


RISKY_PERMISSIONS = {
    Permission.FULL_PROJECT,
    Permission.NETWORK,
    Permission.GIT,
    Permission.CLOUD,
    Permission.DEPLOY,
}


@dataclass(frozen=True)
class ActionRequest:
    action: str
    permission: Permission
    summary: str
    details: dict = field(default_factory=dict)

    @property
    def requires_approval(self) -> bool:
        return self.permission in RISKY_PERMISSIONS


def normalize_permission(value: str | Permission) -> Permission:
    if isinstance(value, Permission):
        return value
    return Permission(str(value).strip().lower())
