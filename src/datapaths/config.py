from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import yaml

from .exceptions import ConfigError

DEFAULT_ROOTS_FILE = "configs/roots.local.yaml"
DEFAULT_REGISTRY_FILE = "configs/artifacts_registry.yaml"

@dataclass(frozen=True)
class DatapathsConfig:
    roots_file: Path
    registry_file: Path

def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
    raise ConfigError(
        "Cannot detect repository root (no pyproject.toml or .git found).\n"
        "Run from the repository root or pass repo_root=Path(...) explicitly."
    )


def load_config(
    repo_root: Path | None = None,
    roots_file: str = DEFAULT_ROOTS_FILE,
    registry_file: str = DEFAULT_REGISTRY_FILE,
) -> DatapathsConfig:
    rr = repo_root.resolve() if repo_root else find_repo_root()
    return DatapathsConfig(
        roots_file=(rr / roots_file).resolve(),
        registry_file=(rr / registry_file).resolve(),
    )

def load_roots(cfg: DatapathsConfig) -> dict[str, Path]:
    if not cfg.roots_file.exists():
        raise ConfigError(
            f"roots.local.yaml not found at {cfg.roots_file}. "
            "Create it (not committed) with absolute paths."
        )
    data = yaml.safe_load(cfg.roots_file.read_text()) or {}
    if not isinstance(data, dict) or not data:
        raise ConfigError(f"Invalid roots file: {cfg.roots_file}")
    roots: dict[str, Path] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, (str, Path)):
            continue
        roots[k] = Path(v).expanduser().resolve()
    return roots
