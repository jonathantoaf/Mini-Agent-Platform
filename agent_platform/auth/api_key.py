"""API key authentication for multi-tenant access."""

import json
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from agent_platform.logging_context import set_tenant_id
from agent_platform.settings import get_settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _load_api_keys() -> dict[str, str]:
    """Load API key → tenant_id mapping from settings.

    Returns:
        Dict mapping API keys to tenant IDs.
    """
    settings = get_settings()
    try:
        return json.loads(settings.api_keys)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse API_KEYS setting. No API keys configured.")
        return {}


async def get_current_tenant_id(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str:
    """Extract and validate tenant ID from API key header.

    Args:
        api_key: The API key from the X-API-Key header.

    Returns:
        The tenant_id associated with the API key.

    Raises:
        HTTPException: 401 if the API key is missing or invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    api_keys = _load_api_keys()
    tenant_id = api_keys.get(api_key)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    request.state.tenant_id = tenant_id
    set_tenant_id(tenant_id)
    return tenant_id


# Type alias for use in route function signatures (mirrors CurrentUserId pattern)
TenantId = Annotated[str, Depends(get_current_tenant_id)]
