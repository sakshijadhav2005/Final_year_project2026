import uuid
from fastapi.testclient import TestClient
from app.main import app


def test_admin_role_management_and_rbac():
    client = TestClient(app)

    # 1. Register Bootstrap Admin
    admin_email = "admin@example.com"
    reg_admin = client.post(
        "/api/v1/auth/register",
        json={"email": admin_email, "password": "password123", "role": "admin"},
    )
    if reg_admin.status_code == 201:
        admin_token = reg_admin.json()["access_token"]
        admin_id = reg_admin.json()["user"]["id"]
    else:
        log_admin = client.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": "password123"},
        )
        admin_token = log_admin.json()["access_token"]
        admin_id = log_admin.json()["user"]["id"]

    # 2. Register Regular User
    user_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    reg_user = client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "password123", "role": "regular_user"},
    )
    assert reg_user.status_code == 201
    user_token = reg_user.json()["access_token"]
    user_id = reg_user.json()["user"]["id"]

    # 3. Register Event Organizer
    org_email = f"org_{uuid.uuid4().hex[:8]}@example.com"
    reg_org = client.post(
        "/api/v1/auth/register",
        json={"email": org_email, "password": "password123", "role": "event_organizer"},
    )
    assert reg_org.status_code == 201
    org_token = reg_org.json()["access_token"]
    org_id = reg_org.json()["user"]["id"]

    # ----------------------------------------------------
    # Case 1: Admin can GET /api/v1/admin/users -> 200
    # ----------------------------------------------------
    res_list_admin = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_list_admin.status_code == 200
    users_list = res_list_admin.json()
    assert isinstance(users_list, list)
    assert any(u["id"] == user_id for u in users_list)
    assert any(u["id"] == org_id for u in users_list)
    # Confirm passwords / sensitive tokens not leaked
    for u in users_list:
        assert "hashed_password" not in u
        assert "password" not in u
        assert "refresh_token" not in u

    # ----------------------------------------------------
    # Case 2: Regular user cannot GET /api/v1/admin/users -> 403
    # ----------------------------------------------------
    res_list_reg = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res_list_reg.status_code == 403

    # ----------------------------------------------------
    # Case 3: Organizer cannot GET /api/v1/admin/users -> 403
    # ----------------------------------------------------
    res_list_org = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {org_token}"},
    )
    assert res_list_org.status_code == 403

    # ----------------------------------------------------
    # Case 4: Admin can change another user's role -> 200
    # Promote regular_user to content_creator
    # ----------------------------------------------------
    res_role_change = client.post(
        f"/api/v1/admin/users/{user_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "content_creator"},
    )
    assert res_role_change.status_code == 200
    updated_user = res_role_change.json()
    assert updated_user["id"] == user_id
    assert updated_user["role"] == "content_creator"

    # ----------------------------------------------------
    # Case 5: Invalid/nonexistent user -> 404
    # ----------------------------------------------------
    fake_uuid = str(uuid.uuid4())
    res_fake_user = client.post(
        f"/api/v1/admin/users/{fake_uuid}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "event_organizer"},
    )
    assert res_fake_user.status_code == 404

    # ----------------------------------------------------
    # Case 6: Regular user cannot change roles -> 403
    # ----------------------------------------------------
    res_user_forbidden = client.post(
        f"/api/v1/admin/users/{org_id}/role",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"role": "admin"},
    )
    assert res_user_forbidden.status_code == 403

    # ----------------------------------------------------
    # Case 7: Organizer cannot change roles -> 403
    # ----------------------------------------------------
    res_org_forbidden = client.post(
        f"/api/v1/admin/users/{user_id}/role",
        headers={"Authorization": f"Bearer {org_token}"},
        json={"role": "admin"},
    )
    assert res_org_forbidden.status_code == 403

    # ----------------------------------------------------
    # Case 8: Admin cannot change their own role -> 403
    # ----------------------------------------------------
    res_self_demote = client.post(
        f"/api/v1/admin/users/{admin_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "regular_user"},
    )
    assert res_self_demote.status_code == 403
    assert "own role" in res_self_demote.json()["detail"].lower()

    # ----------------------------------------------------
    # Case 9: Bootstrap admin cannot have their role changed -> 403
    # ----------------------------------------------------
    # (Even if another admin attempts to demote bootstrap admin)
    # Create second admin account via role promotion
    res_promote_second_admin = client.post(
        f"/api/v1/admin/users/{org_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    assert res_promote_second_admin.status_code == 200

    # Log in as the second admin
    log_second_admin = client.post(
        "/api/v1/auth/login",
        json={"email": org_email, "password": "password123"},
    )
    second_admin_token = log_second_admin.json()["access_token"]

    # Second admin tries to change bootstrap admin's role -> 403
    res_change_bootstrap = client.post(
        f"/api/v1/admin/users/{admin_id}/role",
        headers={"Authorization": f"Bearer {second_admin_token}"},
        json={"role": "regular_user"},
    )
    assert res_change_bootstrap.status_code == 403
    assert "bootstrap" in res_change_bootstrap.json()["detail"].lower()

    # ----------------------------------------------------
    # Case 10: Successful role change creates an audit entry
    # ----------------------------------------------------
    res_audit = client.get(
        "/api/v1/admin/audit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_audit.status_code == 200
    audit_entries = res_audit.json()
    assert any(
        entry["action"] == "role_change"
        and entry["resource_id"] == user_id
        and "content_creator" in (entry["detail"] or "")
        for entry in audit_entries
    )
