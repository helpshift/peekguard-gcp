import os
import tomllib
import hvac
from enum import StrEnum
from importlib import resources
from typing import Any, Callable, LiteralString

from peekguard.utils.logger import get_logger

_logger = get_logger(__name__)

_config: dict[str, Any] = {}

vault_client = None


class Environment(StrEnum):
    LOCALHOST = "localhost"
    SANDBOX = "sandbox"
    PRODUCTION = "nv_prod"


def current_environment() -> Environment:
    hsft_conf_env = os.getenv("HSFT_CONF_ENV", "localhost")
    try:
        return Environment(hsft_conf_env)
    except ValueError:
        _logger.error(
            "Invalid HSFT_CONF_ENV: '%s', using 'localhost' instead", hsft_conf_env
        )
        return Environment.LOCALHOST


def get_vault_client():
    global vault_client
    return vault_client


def get_secret_from_vault(keypath, key, mount_point):
    global vault_client
    secret_response = vault_client.secrets.kv.v2.read_secret_version(
        path=keypath, mount_point=mount_point
    )
    return secret_response["data"]["data"][key]


def _load_config():
    global _config

    environment = current_environment()
    config_package = "peekguard.resources.config"
    config_file = f"{environment}.toml"
    _config = tomllib.loads(
        resources.read_text(package=config_package, resource=config_file)
    )
    assert _config, (
        f"Invalid config for '{environment}' from '{config_package}:{config_file}':\n{_config}"
    )
    _logger.info(
        "Successfully loaded configuration for '%s' from '%s:%s'",
        environment,
        config_package,
        config_file,
    )


def get_config[T](key: LiteralString, coerce: Callable[[Any], T] = str) -> T:
    """Return config field based on environment

    :param key: Dot-separated key for the config e.g. "yugabyte.host", "yugabyte.pool.min_size"
    :param coerce: Callable that converts config value into a specific type (Default: str)
    """
    assert key, f"Invalid config key '{key}'"

    if not _config:
        _load_config()

    result = _config
    try:
        for k in key.split("."):
            result = result[k]
    except KeyError as ke:
        _logger.exception("Unknown config '%s'", key)
        raise ke
    return coerce(result)


def init_vault_client():
    """Init vault client object and return it"""
    global vault_client
    vault_client = hvac.Client(
        url=get_config("vault", "endpoint"),
        token=os.environ["HS_VAULT_TOKEN"],
        verify=get_config("vault", "cert_path"),
    )

    if vault_client.is_authenticated():
        _logger.info("Vault authentication successful")
    else:
        _logger.critical("Vault authentication failed")
        # Raise assert error if vault_client is not authenticated
        assert vault_client.is_authenticated()