import re
import json

from fastapi import APIRouter, Response, Header

from core.globals import SECRET_KEY
from core.repositories.users_repository import UsersRepository


class AuthRouter(APIRouter):
    def __init__(
            self,
            users_repository: UsersRepository,
            *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.users_repository = users_repository

    async def _check_auth(
            self,
            authorization: Header = None,
            accept_secret: bool = False
    ) -> bool:
        if not authorization:
            return False

        match = re.match(r"^Bearer\s+(.+)$", authorization)
        if not match:
            return False

        api_key = match.group(1)
        if api_key == SECRET_KEY and accept_secret:
            return True

        data = await self.users_repository.list_keys()
        if any([d["api_key"] == api_key for d in data]):
            return True

        return False

    def _auth_error_response(self):
        return Response(
            status_code=401,
            content=json.dumps({
                "error": {
                    "message": "Invalid authentication",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key"
                }
            }),
            media_type="application/json"
        )
