import os
import json
import asyncio
from typing import Optional, Dict, Any

import aiohttp
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import clear
from tabulate import tabulate


class ApiManager:
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

    async def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.admin_key}"}

        async with getattr(self.session, method)(url, headers=headers, json=data) as response:
            result = await response.json()
            if response.status != 200:
                raise Exception(f"API error: {json.dumps(result, indent=2)}")
            return result

    async def list_users(self) -> Dict[str, Any]:
        return await self._make_request("get", "/v1/users-list")

    async def create_user(self, email: str) -> Dict[str, Any]:
        return await self._make_request("post", "/v1/users-create", {"email": email})

    async def update_user(self, user_id: int, email: str) -> Dict[str, Any]:
        return await self._make_request("post", "/v1/users-update", {
            "user_id": user_id,
            "email": email
        })

    async def delete_user(self, user_id: int) -> Dict[str, Any]:
        return await self._make_request("post", "/v1/users-delete", {"user_id": user_id})

    async def list_keys(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        data = {"user_id": user_id} if user_id is not None else {}
        return await self._make_request("post", "/v1/keys-list", data)

    async def create_key(self, user_id: int, scope: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        data = {"user_id": user_id, "scope": scope}
        if api_key:
            data["api_key"] = api_key
        return await self._make_request("post", "/v1/keys-create", data)

    async def update_key(self, user_id: int, api_key: str, scope: str) -> Dict[str, Any]:
        return await self._make_request("post", "/v1/keys-update", {
            "user_id": user_id,
            "api_key": api_key,
            "scope": scope
        })

    async def delete_key(self, user_id: int, api_key: str) -> Dict[str, Any]:
        return await self._make_request("post", "/v1/keys-delete", {
            "user_id": user_id,
            "api_key": api_key
        })


class InteractiveCLI:
    def __init__(self):
        self.api = None
        self.session = PromptSession()
        self.main_menu_completer = WordCompleter([
            'users', 'keys', 'settings', 'help', 'exit'
        ])
        self.users_menu_completer = WordCompleter([
            'list', 'create', 'update', 'delete', 'back', 'help'
        ])
        self.keys_menu_completer = WordCompleter([
            'list', 'create', 'update', 'delete', 'back', 'help'
        ])
        self.settings_menu_completer = WordCompleter([
            'show', 'update', 'back', 'help'
        ])
        self.base_url = 'http://localhost:7012'
        self.admin_key = os.environ.get('LLM_PROXY_SECRET', '')

    async def prompt(self, text: str, completer=None) -> str:
        return await self.session.prompt_async(f"{text}: ", completer=completer)

    def print_header(self, text: str):
        clear()
        print(f"\n=== {text} ===\n")

    def print_help(self, commands: Dict[str, str]):
        print("\nAvailable commands:")
        for cmd, desc in commands.items():
            print(f"  {cmd:<10} - {desc}")
        print()

    async def handle_users_menu(self):
        commands = {
            'list': 'List all users',
            'create': 'Create a new user',
            'update': 'Update user email',
            'delete': 'Delete a user',
            'back': 'Return to main menu',
            'help': 'Show this help message'
        }

        while True:
            self.print_header("User Management")
            cmd = await self.prompt("Command", self.users_menu_completer)

            try:
                if cmd == 'list':
                    result = await self.api.list_users()
                    users = result['data']
                    if users:
                        print(tabulate(
                            users,
                            headers={'user_id': 'ID', 'email': 'Email', 'created_at': 'Created At'},
                            tablefmt='psql'
                        ))
                    else:
                        print("No users found")

                elif cmd == 'create':
                    email = await self.prompt("Enter email")
                    result = await self.api.create_user(email)
                    print(f"User created: {json.dumps(result['data'], indent=2)}")

                elif cmd == 'update':
                    user_id = int(await self.prompt("Enter user ID"))
                    email = await self.prompt("Enter new email")
                    result = await self.api.update_user(user_id, email)
                    print(f"User updated: {json.dumps(result['data'], indent=2)}")

                elif cmd == 'delete':
                    user_id = int(await self.prompt("Enter user ID"))
                    await self.api.delete_user(user_id)
                    print(f"User {user_id} deleted successfully")

                elif cmd == 'help':
                    self.print_help(commands)

                elif cmd == 'back':
                    break

            except Exception as e:
                print(f"Error: {str(e)}")

            input("\nPress Enter to continue...")

    async def handle_keys_menu(self):
        commands = {
            'list': 'List API keys',
            'create': 'Create a new API key',
            'update': 'Update API key scope',
            'delete': 'Delete an API key',
            'back': 'Return to main menu',
            'help': 'Show this help message'
        }

        while True:
            self.print_header("API Key Management")
            cmd = await self.prompt("Command", self.keys_menu_completer)

            try:
                if cmd == 'list':
                    user_input = await self.prompt("Enter user ID (or press Enter for all)")
                    user_id = int(user_input) if user_input.strip() else None
                    result = await self.api.list_keys(user_id)
                    keys = result['data']
                    if keys:
                        print(tabulate(
                            keys,
                            headers={
                                'api_key': 'API Key',
                                'scope': 'Scope',
                                'user_id': 'User ID',
                                'user_email': 'User Email',
                                'created_at': 'Created At'
                            },
                            tablefmt='psql'
                        ))
                    else:
                        print("No API keys found")

                elif cmd == 'create':
                    user_id = int(await self.prompt("Enter user ID"))
                    scope = await self.prompt("Enter scope")
                    custom_key = await self.prompt("Enter custom API key (or press Enter for auto-generated)")
                    api_key = custom_key if custom_key.strip() else None
                    result = await self.api.create_key(user_id, scope, api_key)
                    print(f"API key created: {json.dumps(result['data'], indent=2)}")

                elif cmd == 'update':
                    user_id = int(await self.prompt("Enter user ID"))
                    api_key = await self.prompt("Enter API key")
                    scope = await self.prompt("Enter new scope")
                    await self.api.update_key(user_id, api_key, scope)
                    print(f"API key {api_key} updated successfully")

                elif cmd == 'delete':
                    user_id = int(await self.prompt("Enter user ID"))
                    api_key = await self.prompt("Enter API key")
                    await self.api.delete_key(user_id, api_key)
                    print(f"API key {api_key} deleted successfully")

                elif cmd == 'help':
                    self.print_help(commands)

                elif cmd == 'back':
                    break

            except Exception as e:
                print(f"Error: {str(e)}")

            input("\nPress Enter to continue...")

    async def handle_settings_menu(self):
        commands = {
            'show': 'Show current settings',
            'update': 'Update settings',
            'back': 'Return to main menu',
            'help': 'Show this help message'
        }

        while True:
            self.print_header("Settings")
            cmd = await self.prompt("Command", self.settings_menu_completer)

            if cmd == 'show':
                print(f"\nAPI URL: {self.base_url}")
                print(f"Admin Key: {self.admin_key[:8]}..." if self.admin_key else "Admin Key: not set")

            elif cmd == 'update':
                new_url = await self.prompt(f"Enter API URL [{self.base_url}]")
                self.base_url = new_url if new_url.strip() else self.base_url
                admin_key = await self.prompt("Enter admin key (press Enter to keep current)")
                if admin_key.strip():
                    self.admin_key = admin_key
                # Recreate API manager with new settings
                self.api = ApiManager(self.base_url, self.admin_key)
                print("\nSettings updated successfully")
            elif cmd == 'help':
                self.print_help(commands)

            elif cmd == 'back':
                break

            input("\nPress Enter to continue...")

    async def main_menu(self):
        commands = {
            'users': 'Manage users',
            'keys': 'Manage API keys',
            'settings': 'Configure settings',
            'help': 'Show this help message',
            'exit': 'Exit the program'
        }

        while True:
            self.print_header("Main Menu")
            cmd = await self.prompt("Command", self.main_menu_completer)

            if cmd == 'users':
                await self.handle_users_menu()
            elif cmd == 'keys':
                await self.handle_keys_menu()
            elif cmd == 'settings':
                await self.handle_settings_menu()
            elif cmd == 'help':
                self.print_help(commands)
            elif cmd == 'exit':
                break

    async def run(self):
        print("\nWelcome to the API Management CLI!")

        # Initialize settings if not set
        if not self.admin_key:
            print("\nNo admin key found. Please configure settings first.")
            self.admin_key = await self.prompt("Enter admin key")

        self.api = ApiManager(self.base_url, self.admin_key)
        async with self.api:
            await self.main_menu()

        print("\nGoodbye!")


if __name__ == '__main__':
    try:
        cli = InteractiveCLI()
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nError: {str(e)}")
