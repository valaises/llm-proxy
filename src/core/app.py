from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from core.models import AssetsModels
from core.repositories.users_repository import UsersRepository
from core.routers.router_chat_completions import ChatCompletionsRouter
from core.routers.router_models import ModelsRouter
from core.routers.router_users import UsersRouter


__all__ = ["App"]


class App(FastAPI):
    def __init__(
            self,
            db_dir: Path,
            a_models: AssetsModels,
            *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._a_models = a_models
        self._users_repository = UsersRepository(db_dir / "users.db")

        self._setup_middlewares()
        self.add_event_handler("startup", self._startup_events)

        for router in self._routers():
            self.include_router(router)

    def _setup_middlewares(self):
        self.add_middleware(
            CORSMiddleware, # type: ignore[arg-type]
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.add_middleware(NoCacheMiddleware) # type: ignore[arg-type]

    async def _startup_events(self):
        pass

    def _routers(self):
        return [
            ModelsRouter(
                self._a_models,
                self._users_repository
            ),
            ChatCompletionsRouter(
                self._a_models,
                self._users_repository
            ),
            UsersRouter(
                self._users_repository
            ),
        ]

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response
