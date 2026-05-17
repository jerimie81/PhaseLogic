from phaselogic.connectors.base import BaseConnector
from phaselogic.connectors.github import GitHubConnector
from phaselogic.connectors.local_git import LocalGitConnector


_CONNECTORS: dict[str, type[BaseConnector]] = {
    GitHubConnector.name: GitHubConnector,
    LocalGitConnector.name: LocalGitConnector,
}


def list_connectors() -> list[BaseConnector]:
    return [connector_cls() for connector_cls in _CONNECTORS.values()]


def get_connector(name: str) -> BaseConnector:
    key = name.strip().lower()
    try:
        return _CONNECTORS[key]()
    except KeyError:
        known = ", ".join(sorted(_CONNECTORS))
        raise ValueError(f"Unknown connector '{name}'. Known connectors: {known}")
