"""Settings for the CLIs (API keys, URLs, document ids): an environment
variable if set, otherwise the config file -- so every script reports
missing settings the same way instead of hand-rolling it.

The config file is TOML, the first that exists of:
  $BSCLI_CONFIG (also set by `bscli --config PATH`)
  $XDG_CONFIG_HOME/bscli/config.toml
  ~/.config/bscli/config.toml

  [grist]
  base_url = "https://docs.getgrist.com"
  doc_id = "DOC_ID"
  api_key_cmd = ["gopass", "show", "grist-api-key"]

  [lexware]
  api_key_cmd = ["gopass", "show", "lexware-api-key"]

Any value can be given as `<key>_cmd` instead of `<key>`: a command, run
without a shell, whose output is the value -- so secrets stay in gopass (or
the like) and out of the file. Each command runs at most once per process.
See bscli.example.toml next to pyproject.toml.
"""

import functools
import logging
import os
import shlex
import stat
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Environment variable -> (config section, key).
SETTINGS = frozendict(
    {
        "GRIST_BASE_URL": ("grist", "base_url"),
        "GRIST_DOC_ID": ("grist", "doc_id"),
        "GRIST_API_KEY": ("grist", "api_key"),
        "LEXWARE_API_KEY": ("lexware", "api_key"),
    }
)


def config_path() -> Path:
    """Where the config file is looked for (it need not exist)."""
    if explicit := os.environ.get("BSCLI_CONFIG"):
        return Path(explicit).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "bscli" / "config.toml"


@functools.cache
def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        if os.environ.get("BSCLI_CONFIG"):
            logger.error("Config file %s does not exist.", path)
            sys.exit(1)
        return {}
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        logger.error("Cannot read config file %s: %s", path, exc)
        sys.exit(1)
    if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO) and _has_plain_secret(config):
        logger.warning(
            "%s holds a plain api_key and is readable by others -- chmod 600 it, "
            "or use api_key_cmd.",
            path,
        )
    return config


def _has_plain_secret(config: dict[str, Any]) -> bool:
    return any(isinstance(sec, dict) and "api_key" in sec for sec in config.values())


@functools.cache
def _from_config(name: str) -> str | None:
    section, key = SETTINGS[name]
    values = load_config().get(section, {})
    if not isinstance(values, dict):
        return None
    if key in values:
        return str(values[key])
    if (cmd := values.get(f"{key}_cmd")) is None:
        return None
    argv = shlex.split(cmd) if isinstance(cmd, str) else [str(a) for a in cmd]
    try:
        result = subprocess.run(argv, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        logger.error("%s.%s_cmd %s failed: %s %s", section, key, argv, exc, stderr.strip())
        sys.exit(1)
    return result.stdout.strip() or None


def require_env(*names: str) -> dict[str, str]:
    """Returns {name: value} for every setting in `names` -- from the
    environment, else from the config file -- or logs which ones are
    missing (and where they could go) and exits(1).
    """
    values: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        value = os.environ.get(name) or (_from_config(name) if name in SETTINGS else None)
        if value:
            values[name] = value
        else:
            missing.append(name)
    if missing:
        hints = [
            f"{n} (or {SETTINGS[n][0]}.{SETTINGS[n][1]} in {config_path()})" if n in SETTINGS else n
            for n in missing
        ]
        logger.error("Missing setting(s): %s", ", ".join(hints))
        sys.exit(1)
    return values


def require_env_var(name: str) -> str:
    return require_env(name)[name]
