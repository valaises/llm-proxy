import json
import secrets

from fastapi import Header
from fastapi.responses import Response

from core.routers.router_auth import AuthRouter
from core.repositories.users_repository import (
    ApiKeyUpdatePost,
    ApiKeyCreatePost,
    ApiKeyDeletePost,
    ApiKeyListPost,
    UserCreatePost,
    UserUpdatePost,
    UserDeletePost
)


class UsersRouter(AuthRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # User management endpoints
        self.add_api_route("/v1/users-list", self._list_users, methods=["GET"])
        self.add_api_route("/v1/users-create", self._create_user, methods=["POST"])
        self.add_api_route("/v1/users-update", self._update_user, methods=["POST"])
        self.add_api_route("/v1/users-delete", self._delete_user, methods=["POST"])

        # API key management endpoints
        self.add_api_route("/v1/keys-list", self._list_keys, methods=["POST"])
        self.add_api_route("/v1/keys-create", self._create_key, methods=["POST"])
        self.add_api_route("/v1/keys-delete", self._delete_key, methods=["POST"])
        self.add_api_route("/v1/keys-update", self._update_key, methods=["POST"])

    async def _list_users(self, authorization: str = Header(None)) -> Response:
        """List all users."""
        if not await self._check_auth(authorization, True):
            return self._auth_error_response()

        users = await self.users_repository.list_users()
        return Response(
            content=json.dumps(
                {
                    "object": "list",
                    "data": users
                },
                indent=2
            ),
            media_type="application/json"
        )

    async def _create_user(
            self,
            post: UserCreatePost,
            authorization: str = Header(None)
    ) -> Response:
        """Create a new user."""
        if not await self._check_auth(authorization, True):
            return self._auth_error_response()

        user = await self.users_repository.create_user(post)
        if not user:
            return Response(
                status_code=400,
                content=json.dumps({
                    "error": {
                        "message": "User with this email already exists",
                        "type": "invalid_request_error",
                        "code": "duplicate_email"
                    }
                }),
                media_type="application/json"
            )

        return Response(
            content=json.dumps({
                "message": "User created successfully",
                "object": "user",
                "data": user
            }, indent=2),
            media_type="application/json"
        )

    async def _update_user(
            self,
            post: UserUpdatePost,
            authorization: str = Header(None)
    ) -> Response:
        """Update a user."""
        if not await self._check_auth(authorization, True):
            return self._auth_error_response()

        user = await self.users_repository.update_user(post)
        if not user:
            return Response(
                status_code=404,
                content=json.dumps({
                    "error": {
                        "message": "User not found or email already exists",
                        "type": "invalid_request_error",
                        "code": "user_error"
                    }
                }),
                media_type="application/json"
            )

        return Response(
            content=json.dumps({
                "message": "User updated successfully",
                "object": "user",
                "data": user
            }, indent=2),
            media_type="application/json"
        )

    async def _delete_user(
            self,
            post: UserDeletePost,
            authorization: str = Header(None)
    ) -> Response:
        """Delete a user."""
        if not await self._check_auth(authorization, True):
            return self._auth_error_response()

        if not await self.users_repository.delete_user(post):
            return Response(
                status_code=404,
                content=json.dumps({
                    "error": {
                        "message": "User not found",
                        "type": "invalid_request_error",
                        "code": "user_not_found"
                    }
                }),
                media_type="application/json"
            )

        return Response(
            content=json.dumps({
                "message": "User deleted successfully"
            }, indent=2),
            media_type="application/json"
        )

    async def _list_keys(
            self,
            post: ApiKeyListPost,
            authorization: str = Header(None)
    ) -> Response:
        """List API keys, optionally filtered by user_id."""
        if not await self._check_auth(authorization, True):
            return self._auth_error_response()

        keys = await self.users_repository.list_keys(post)
        return Response(
            content=json.dumps(
                {
                    "object": "list",
                    "data": keys
                },
                indent=2
            ),
            media_type="application/json"
        )

    async def _create_key(
            self,
            post: ApiKeyCreatePost,
            authorization: str = Header(None)
    ) -> Response:
        """Create a new API key."""
        if not await self._check_auth(authorization, True):
            return self._auth_error_response()

        if not post.api_key:
            post.api_key = f"lpak-{secrets.token_urlsafe(16)}"

        try:
            success = await self.users_repository.create_key(post)
            if not success:
                return Response(
                    status_code=400,
                    content=json.dumps({
                        "error": {
                            "message": "API key already exists",
                            "type": "invalid_request_error",
                            "code": "duplicate_key"
                        }
                    }),
                    media_type="application/json"
                )

        except ValueError as e:
            return Response(
                status_code=400,
                content=json.dumps({
                    "error": {
                        "message": str(e),
                        "type": "invalid_request_error",
                        "code": "invalid_request"
                    }
                }),
                media_type="application/json"
            )

        return Response(
            content=json.dumps({
                "message": "API key created successfully",
                "object": "key",
                "data": {
                    "api_key": post.api_key,
                    "scope": post.scope,
                    "user_id": post.user_id
                }
            }, indent=2),
            media_type="application/json"
        )

    async def _delete_key(
            self,
            post: ApiKeyDeletePost,
            authorization: str = Header(None)
    ) -> Response:
        """Delete an API key."""
        if not await self._check_auth(authorization, True):
            return self._auth_error_response()

        if not await self.users_repository.delete_key(post):
            return Response(
                status_code=404,
                content=json.dumps({
                    "error": {
                        "message": "API key not found or doesn't belong to the specified user",
                        "type": "invalid_request_error",
                        "code": "key_not_found"
                    }
                }),
                media_type="application/json"
            )

        return Response(
            content=json.dumps({
                "message": "API key deleted successfully"
            }, indent=2),
            media_type="application/json"
        )

    async def _update_key(
            self,
            post: ApiKeyUpdatePost,
            authorization: str = Header(None)
    ) -> Response:
        """Update an API key's scope."""
        if not await self._check_auth(authorization, True):
            return self._auth_error_response()

        try:
            success = await self.users_repository.update_key(post)
            if not success:
                return Response(
                    status_code=404,
                    content=json.dumps({
                        "error": {
                            "message": "API key not found or doesn't belong to the specified user",
                            "type": "invalid_request_error",
                            "code": "key_not_found"
                        }
                    }),
                    media_type="application/json"
                )

        except Exception as e:
            return Response(
                status_code=400,
                content=json.dumps({
                    "error": {
                        "message": str(e),
                        "type": "invalid_request_error",
                        "code": "invalid_request"
                    }
                }),
                media_type="application/json"
            )

        return Response(
            content=json.dumps({
                "message": "API key updated successfully"
            }, indent=2),
            media_type="application/json"
        )
