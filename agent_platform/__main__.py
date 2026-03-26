import sys

import uvicorn

from agent_platform.api.server import app
from agent_platform.settings import get_settings


def init() -> None:
    settings = get_settings()
    uvicorn.run(
        "agent_platform.api.server:app",
        host="127.0.0.1",
        port=8000,
        log_level="debug" if settings.debug else "info",
        reload=True,
    )


# To make sure the service will run with uvicorn only when running this service directly
# on the localhost for developing purposes
if __name__ == "__main__":
    app.extra["container"].wire(modules=[sys.modules[__name__]])
    init()
