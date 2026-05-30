import pytest


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()


class TestAuth:
    def test_register_success(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "NewPassword123",
                "full_name": "New User",
                "role": "tester",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "tester"

    def test_register_duplicate_username(self, client, test_user):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "another@example.com",
                "password": "NewPassword123",
            },
        )
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_register_duplicate_email(self, client, test_user):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "anotheruser",
                "email": "test@example.com",
                "password": "NewPassword123",
            },
        )
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_register_password_too_short(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "shortpass",
                "email": "short@example.com",
                "password": "123",
            },
        )
        assert response.status_code == 422

    def test_login_success(self, client, test_user):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "TestPassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_login_invalid_password(self, client, test_user):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "WrongPassword"},
        )
        assert response.status_code == 401
        assert "错误" in response.json()["detail"]

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent", "password": "SomePassword123"},
        )
        assert response.status_code == 401

    def test_login_locked_account(self, client, db):
        from datetime import datetime, timezone, timedelta
        from app.models.user import User, UserRole, UserStatus
        from app.core.security import get_password_hash

        locked_user = User(
            username="lockeduser",
            email="locked@example.com",
            password_hash=get_password_hash("LockedPass123"),
            role=UserRole.VIEWER,
            status=UserStatus.ACTIVE,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(locked_user)
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            data={"username": "lockeduser", "password": "LockedPass123"},
        )
        assert response.status_code == 423
        assert "锁定" in response.json()["detail"]

    def test_login_inactive_account(self, client, db, test_user):
        from app.models.user import UserStatus

        test_user.status = UserStatus.INACTIVE
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "TestPassword123"},
        )
        assert response.status_code == 403
        assert "禁用" in response.json()["detail"]

    def test_get_me(self, client, auth_headers, test_user):
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_get_me_unauthorized(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_logout(self, client, auth_headers):
        response = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        assert "成功" in response.json()["message"]

    def test_change_password_success(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "TestPassword123",
                "new_password": "NewPassword456",
            },
        )
        assert response.status_code == 200
        assert "成功" in response.json()["message"]

    def test_change_password_wrong_current(self, client, auth_headers):
        response = client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "WrongPassword",
                "new_password": "NewPassword456",
            },
        )
        assert response.status_code == 400
        assert "错误" in response.json()["detail"]

    def test_refresh_token(self, client, test_user):
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "TestPassword123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = client.post(
            "/api/v1/auth/refresh",
            params={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_token_invalid(self, client):
        response = client.post(
            "/api/v1/auth/refresh",
            params={"refresh_token": "invalid_token"},
        )
        assert response.status_code == 401
