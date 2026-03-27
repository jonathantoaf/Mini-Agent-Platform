import logging
from contextvars import ContextVar, Token

_DEFAULT_CONTEXT_VALUE = "-"

_request_id: ContextVar[str] = ContextVar("request_id", default=_DEFAULT_CONTEXT_VALUE)
_tenant_id: ContextVar[str] = ContextVar("tenant_id", default=_DEFAULT_CONTEXT_VALUE)


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(request_id: str) -> Token[str]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def get_tenant_id() -> str:
    return _tenant_id.get()


def set_tenant_id(tenant_id: str) -> Token[str]:
    return _tenant_id.set(tenant_id)


def reset_tenant_id(token: Token[str]) -> None:
    _tenant_id.reset(token)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.tenant_id = get_tenant_id()
        return True
