import os
import aiohttp
import asyncio
import json
from typing import Optional, Dict


SECRET_KEY = os.environ.get("LLM_PROXY_SECRET")


class ApiKeysTester:
    def __init__(self, base_url: str, admin_key: str):
        self.base_url = base_url.rstrip('/')
        self.admin_key = admin_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def list_users(self) -> Dict:
        async with self.session.get(
                f"{self.base_url}/v1/users-list",
                headers={"Authorization": f"Bearer {self.admin_key}"}
        ) as response:
            resp = await response.json()
            assert response.status == 200, resp
            return resp

    async def create_user(self, email: str) -> Dict:
        async with self.session.post(
                f"{self.base_url}/v1/users-create",
                headers={"Authorization": f"Bearer {self.admin_key}"},
                json={"email": email}
        ) as response:
            resp = await response.json()
            assert response.status == 200, resp
            return resp

    async def update_user(self, user_id: int, email: str) -> Dict:
        async with self.session.post(
                f"{self.base_url}/v1/users-update",
                headers={"Authorization": f"Bearer {self.admin_key}"},
                json={"user_id": user_id, "email": email}
        ) as response:
            resp = await response.json()
            assert response.status == 200, resp
            return resp

    async def delete_user(self, user_id: int) -> Dict:
        async with self.session.post(
                f"{self.base_url}/v1/users-delete",
                headers={"Authorization": f"Bearer {self.admin_key}"},
                json={"user_id": user_id}
        ) as response:
            resp = await response.json()
            assert response.status == 200, resp
            return resp

    async def list_keys(self, user_id: Optional[int] = None) -> Dict:
        data = {}
        if user_id is not None:
            data["user_id"] = user_id

        async with self.session.post(
                f"{self.base_url}/v1/keys-list",
                headers={"Authorization": f"Bearer {self.admin_key}"},
                json=data
        ) as response:
            resp = await response.json()
            assert response.status == 200, resp
            return resp

    async def create_key(self, user_id: int, api_key: Optional[str], scope: str) -> Dict:
        data = {"user_id": user_id, "scope": scope}
        if api_key:
            data["api_key"] = api_key

        async with self.session.post(
                f"{self.base_url}/v1/keys-create",
                headers={"Authorization": f"Bearer {self.admin_key}"},
                json=data
        ) as response:
            resp = await response.json()
            assert response.status == 200, resp
            return resp

    async def delete_key(self, user_id: int, api_key: str) -> Dict:
        async with self.session.post(
                f"{self.base_url}/v1/keys-delete",
                headers={"Authorization": f"Bearer {self.admin_key}"},
                json={"user_id": user_id, "api_key": api_key}
        ) as response:
            resp = await response.json()
            assert response.status == 200, resp
            return resp

    async def update_key(self, user_id: int, api_key: str, scope: str) -> Dict:
        data = {
            "user_id": user_id,
            "api_key": api_key,
            "scope": scope
        }

        async with self.session.post(
                f"{self.base_url}/v1/keys-update",
                headers={"Authorization": f"Bearer {self.admin_key}"},
                json=data
        ) as response:
            resp = await response.json()
            assert response.status == 200, resp
            return resp


async def run_test_scenario():
    base_url = "http://localhost:7012"

    async with ApiKeysTester(base_url, SECRET_KEY) as tester:
        # Create users
        print("\n1. Creating test users...")
        user1 = await tester.create_user("test1@example.com")
        print("User 1 created:", json.dumps(user1, indent=2))
        user1_id = user1["data"]["user_id"]

        user2 = await tester.create_user("test2@example.com")
        print("User 2 created:", json.dumps(user2, indent=2))
        user2_id = user2["data"]["user_id"]

        # List users
        print("\n2. Listing all users...")
        users = await tester.list_users()
        print("Users list:", json.dumps(users, indent=2))

        # Create keys for users
        print("\n3. Creating keys for users...")
        key1 = await tester.create_key(user1_id, "test-key-1", "read")
        print("Key 1 created:", json.dumps(key1, indent=2))

        key2 = await tester.create_key(user2_id, "test-key-2", "write")
        print("Key 2 created:", json.dumps(key2, indent=2))

        # List keys for specific user
        print("\n4. Listing keys for user 1...")
        keys_user1 = await tester.list_keys(user1_id)
        print("User 1 keys:", json.dumps(keys_user1, indent=2))

        # List all keys
        print("\n5. Listing all keys...")
        all_keys = await tester.list_keys()
        print("All keys:", json.dumps(all_keys, indent=2))

        # Update user
        print("\n6. Updating user 1 email...")
        updated_user = await tester.update_user(user1_id, "test1.updated@example.com")
        print("Updated user:", json.dumps(updated_user, indent=2))

        # Update key
        print("\n7. Updating key for user 1...")
        updated_key = await tester.update_key(user1_id, "test-key-1", "full_access")
        print("Updated key:", json.dumps(updated_key, indent=2))

        # Delete key
        print("\n8. Deleting key from user 1...")
        delete_key_result = await tester.delete_key(user1_id, "test-key-1")
        print("Delete key result:", json.dumps(delete_key_result, indent=2))

        # Try to update non-existent key (should fail)
        print("\n9. Attempting to update non-existent key...")
        try:
            await tester.update_key(user1_id, "test-key-1", "read")
        except AssertionError as e:
            print("Update failed as expected:", str(e))

        # Delete user (should cascade delete their keys)
        print("\n10. Deleting user 2 (should cascade delete their keys)...")
        delete_user_result = await tester.delete_user(user2_id)
        print("Delete user result:", json.dumps(delete_user_result, indent=2))

        # Verify keys are gone
        print("\n11. Verifying keys after user deletion...")
        final_keys = await tester.list_keys()
        print("Final keys list:", json.dumps(final_keys, indent=2))

        # Clean up remaining user
        print("\n12. Cleaning up remaining user...")
        await tester.delete_user(user1_id)

        # Final verification
        print("\n13. Final verification...")
        final_users = await tester.list_users()
        final_keys = await tester.list_keys()
        print("Final users:", json.dumps(final_users, indent=2))
        print("Final keys:", json.dumps(final_keys, indent=2))


if __name__ == "__main__":
    asyncio.run(run_test_scenario())
