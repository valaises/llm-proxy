import json
import time

from fastapi import Header
from fastapi.responses import Response

from core.models import AssetsModels
from core.routers.router_auth import AuthRouter


class ModelsRouter(AuthRouter):
    def __init__(
            self,
            a_models: AssetsModels,
            *args, **kwargs
    ):
        self._a_models = a_models
        super().__init__(*args, **kwargs)

        self._all_models = [
            {
                "model_name": m_name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "system"
            }
            for m_name in [
                *self._a_models.model_defaults.keys(),
                *[i.name for i in self._a_models.model_list]
            ]
        ]

        self.add_api_route("/v1/models", self._models, methods=["GET"])
        self.add_api_route("/v1/models/{model}", self._model_info, methods=["GET"])

    async def _models(self, authorization: str = Header(None)):
        if not await self._check_auth(authorization):
            return self._auth_error_response()

        data = {
            "object": "list",
            "data": self._all_models
        }

        return Response(content=json.dumps(data, indent=2), media_type="application/json")

    async def _model_info(self, model: str, authorization: str = Header(None)):
        if not await self._check_auth(authorization):
            return self._auth_error_response()

        models = [m for m in self._all_models if m["model_name"] == model]
        if not models:
            return Response(
                status_code=404,
                content=json.dumps({
                    "error": {
                        "message": "Model not found",
                        "type": "invalid_request_error",
                        "code": "model_not_found"
                    }
                }),
                media_type="application/json"
            )

        return Response(content=json.dumps(models[0], indent=2), media_type="application/json")
