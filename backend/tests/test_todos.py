"""Todo tests."""

import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str = "todo@example.com") -> str:
    """Helper to register and get auth token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient):
    """Test creating a new todo."""
    token = await get_auth_token(client, "create@example.com")

    response = await client.post(
        "/api/v1/todos",
        json={"title": "Test Todo", "description": "A test todo item"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "A test todo item"
    assert data["completed"] is False


@pytest.mark.asyncio
async def test_get_todos(client: AsyncClient):
    """Test getting todo list."""
    token = await get_auth_token(client, "list@example.com")

    # Create a todo first
    await client.post(
        "/api/v1/todos",
        json={"title": "List Todo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get todos
    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_update_todo(client: AsyncClient):
    """Test updating a todo."""
    token = await get_auth_token(client, "update@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Update Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Update it
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated Title", "completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_todo(client: AsyncClient):
    """Test deleting a todo."""
    token = await get_auth_token(client, "delete@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Delete Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Delete it
    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_cannot_read_other_users_todo(client: AsyncClient):
    """IDOR regression: GET /todos/{id} must not return another user's todo."""
    owner_token = await get_auth_token(client, "owner-read@example.com")
    attacker_token = await get_auth_token(client, "attacker-read@example.com")

    created = await client.post(
        "/api/v1/todos",
        json={"title": "Owner secret"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    todo_id = created.json()["id"]

    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_cannot_update_other_users_todo(client: AsyncClient):
    """IDOR regression: PUT /todos/{id} must not modify another user's todo."""
    owner_token = await get_auth_token(client, "owner-update@example.com")
    attacker_token = await get_auth_token(client, "attacker-update@example.com")

    created = await client.post(
        "/api/v1/todos",
        json={"title": "Untouched"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    todo_id = created.json()["id"]

    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Hacked", "completed": True},
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert response.status_code == 404, response.text

    # Owner still sees original
    owner_view = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_view.status_code == 200
    assert owner_view.json()["title"] == "Untouched"


@pytest.mark.asyncio
async def test_cannot_delete_other_users_todo(client: AsyncClient):
    """IDOR regression: DELETE /todos/{id} must not remove another user's todo."""
    owner_token = await get_auth_token(client, "owner-delete@example.com")
    attacker_token = await get_auth_token(client, "attacker-delete@example.com")

    created = await client.post(
        "/api/v1/todos",
        json={"title": "Keep me"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    todo_id = created.json()["id"]

    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert response.status_code == 404, response.text

    # Owner can still see it
    owner_view = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_view.status_code == 200


@pytest.mark.asyncio
async def test_get_single_todo(client: AsyncClient):
    """Test getting a single todo by ID."""
    token = await get_auth_token(client, "single@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Single Todo", "description": "Get me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Get it
    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Single Todo"
