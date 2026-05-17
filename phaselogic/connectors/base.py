from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from phaselogic.permissions import Permission


@dataclass(frozen=True)
class ConnectorCapability:
    name: str
    description: str
    permissions: tuple[Permission, ...] = ()


@dataclass(frozen=True)
class ConnectorStatus:
    name: str
    connected: bool
    detail: str
    capabilities: tuple[ConnectorCapability, ...] = field(default_factory=tuple)


class BaseConnector(ABC):
    name: str = "base"
    display_name: str = "Base Connector"

    @classmethod
    @abstractmethod
    def capabilities(cls) -> tuple[ConnectorCapability, ...]:
        """Return the actions this connector can support."""

    @abstractmethod
    def health_check(self) -> ConnectorStatus:
        """Return whether this connector is locally usable."""

    def connect(self) -> ConnectorStatus:
        """Perform any local auth/setup handshake needed by the connector."""
        return self.health_check()
