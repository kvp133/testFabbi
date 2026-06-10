"""Auth tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login after registration."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "password123"},
    )

    # Then login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient):
    """Test getting current user info."""
    # Register and get token
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    token = reg_response.json()["access_token"]

    # Get current user
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout endpoint."""
    # Register and get token
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "logout@example.com", "password": "password123"},
    )
    token = reg_response.json()["access_token"]

    # Logout
    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"


@pytest.mark.asyncio
async def test_access_token_revoked_after_logout(client: AsyncClient):
    """After /auth/logout the access token must no longer authenticate."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "revoke@example.com", "password": "password123"},
    )
    access = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # Sanity: token works before logout
    me_before = await client.get("/api/v1/auth/me", headers=headers)
    assert me_before.status_code == 200

    logout = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 200

    me_after = await client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401, me_after.text
    assert "revoked" in me_after.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_token_revoked_after_logout(client: AsyncClient):
    """Logout with refresh_token body must also revoke the refresh token."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "rev-refresh@example.com", "password": "password123"},
    )
    access = reg.json()["access_token"]
    refresh = reg.json()["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
        json={"refresh_token": refresh},
    )
    assert logout.status_code == 200

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert response.status_code == 401, response.text
    assert "revoked" in response.json()["detail"].lower()
