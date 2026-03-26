import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from agent_platform.api.server import app
from agent_platform.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    uvicorn.run(app, host=settings.server_host, port=settings.server_port)
