import inspect
import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agent_platform.api import dependencies
from agent_platform.api.routers import (
    agent_router,
    health_router,
    index_router,
    run_router,
    tool_router,
)
from agent_platform.containers import Container
from agent_platform.logging_context import (
    reset_request_id,
    reset_tenant_id,
    set_request_id,
    set_tenant_id,
)
from agent_platform.settings import get_settings

logger = logging.getLogger(__name__)


async def _await_if_needed(value: object) -> None:
    if inspect.isawaitable(value):
        await value


def create_container() -> Container:
    settings = get_settings()
    container = Container()
    config_path = os.path.join(settings.root_dir, "config.yaml")
    container.config.from_yaml(config_path, required=True)
    container.config.database_url.from_value(settings.database_url)
    container.config.database_pool_size.from_value(settings.database_pool_size)
    container.config.database_max_overflow.from_value(settings.database_max_overflow)
    container.config.debug.from_value(settings.debug)
    container.wire(
        modules=[dependencies, index_router, health_router, tool_router, agent_router, run_router]
    )
    return container


def create_app() -> FastAPI:
    settings = get_settings()
    container = create_container()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await _await_if_needed(container.init_resources())
        db = container.db()
        logger.info(f"Starting FastAPI server {settings.app_name} v{settings.app_version}...")
        logger.info(
            f"FastAPI server {settings.app_name} v{settings.app_version} is up and running!"
        )
        try:
            yield
        finally:
            logger.info(
                f"Shutting down FastAPI server {settings.app_name} v{settings.app_version}..."
            )
            await db.dispose()
            await _await_if_needed(container.shutdown_resources())

    _app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        root_path=settings.server_root_path,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    _app.extra = {"container": container}
    _app.include_router(index_router.router)
    _app.include_router(health_router.router)
    _app.include_router(tool_router.router, prefix="/api/v1")
    _app.include_router(agent_router.router, prefix="/api/v1")
    _app.include_router(run_router.router, prefix="/api/v1")

    async def exception_handler(request: Request, _error: Exception) -> JSONResponse:
        logger.exception(
            f"Unhandled exception method={request.method.upper()} path={request.url.path}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )

    def custom_swagger_ui_html() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=f"{_app.root_path}{_app.openapi_url}",
            title=_app.title + " - Swagger UI",
            oauth2_redirect_url=_app.swagger_ui_oauth2_redirect_url,
            swagger_js_url=f"{_app.root_path}/static/swagger-ui-bundle.js",
            swagger_css_url=f"{_app.root_path}/static/swagger-ui.css",
            swagger_favicon_url=f"{_app.root_path}/static/favicon.png",
        )

    def redoc_html() -> HTMLResponse:
        return get_redoc_html(
            openapi_url=f"{_app.root_path}{_app.openapi_url}",
            title=_app.title + " - ReDoc",
            redoc_js_url=f"{_app.root_path}/static/redoc.standalone.js",
            redoc_favicon_url=f"{_app.root_path}/static/favicon.png",
        )

    @_app.middleware("http")
    async def add_process_time_header(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id_token = set_request_id(uuid.uuid4().hex[:8])
        tenant_id_token = set_tenant_id("-")
        start_time = time.perf_counter()

        logger.info(f"Request started method={request.method.upper()} path={request.url.path}")

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            response.headers["X-Process-Time"] = f"{duration_ms:.2f}"
            completion_tenant_id = getattr(request.state, "tenant_id", "-")
            completion_tenant_token = set_tenant_id(completion_tenant_id)
            try:
                logger.info(
                    f"Request completed method={request.method.upper()} path={request.url.path} "
                    f"status_code={response.status_code} duration_ms={duration_ms:.2f}"
                )
            finally:
                reset_tenant_id(completion_tenant_token)
            return response
        finally:
            reset_tenant_id(tenant_id_token)
            reset_request_id(request_id_token)

    static_folder = os.path.join(settings.root_dir, "api/static")
    _app.mount("/static", StaticFiles(directory=static_folder), name="static")
    _app.add_exception_handler(Exception, exception_handler)
    _app.add_api_route("/docs", custom_swagger_ui_html, include_in_schema=False)
    _app.add_api_route("/redoc", redoc_html, include_in_schema=False)

    return _app


app = create_app()
