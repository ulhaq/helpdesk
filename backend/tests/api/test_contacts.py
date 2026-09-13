from fastapi.testclient import TestClient


def _create(client: TestClient, name: str, email: str) -> dict:
    response = client.post("/v1/contacts", json={"name": name, "email": email})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_a_contact(admin_authenticated: TestClient) -> None:
    rs = _create(admin_authenticated, "Jane Customer", "Jane@Example.org")

    assert rs["id"]
    assert rs["name"] == "Jane Customer"
    # Emails are normalized so matching a returning customer is case-insensitive.
    assert rs["email"] == "jane@example.org"
    assert rs["organization_id"] == 1


def test_contact_email_is_unique_per_organization(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    _create(admin_authenticated, "Jane", "jane@example.org")

    response = admin_authenticated.post(
        "/v1/contacts", json={"name": "Jane again", "email": "JANE@example.org"}
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "contact_email_taken"

    # Another organization may hold its own contact with the same email.
    _create(organization2_admin_authenticated, "Jane", "jane@example.org")


def test_search_contacts(admin_authenticated: TestClient) -> None:
    _create(admin_authenticated, "Jane", "jane@example.org")
    _create(admin_authenticated, "John", "john@example.org")

    response = admin_authenticated.get("/v1/contacts?q=john")
    assert response.status_code == 200
    assert [c["name"] for c in response.json()["items"]] == ["John"]


def test_patch_a_contact(admin_authenticated: TestClient) -> None:
    created = _create(admin_authenticated, "Jane", "jane@example.org")

    response = admin_authenticated.patch(
        f"/v1/contacts/{created['id']}", json={"notes": "VIP", "locale": "da"}
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "VIP"
    assert response.json()["locale"] == "da"


def test_delete_a_contact(admin_authenticated: TestClient) -> None:
    created = _create(admin_authenticated, "Jane", "jane@example.org")

    response = admin_authenticated.delete(f"/v1/contacts/{created['id']}")
    assert response.status_code == 204
    response = admin_authenticated.get(f"/v1/contacts/{created['id']}")
    assert response.status_code == 404


def test_contacts_are_isolated_between_organizations(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    created = _create(admin_authenticated, "Jane", "jane@example.org")

    response = organization2_admin_authenticated.get(f"/v1/contacts/{created['id']}")
    assert response.status_code == 404
    response = organization2_admin_authenticated.get("/v1/contacts")
    assert response.json()["total"] == 0


def test_contacts_require_permission(no_roles_authenticated: TestClient) -> None:
    assert no_roles_authenticated.get("/v1/contacts").status_code == 403
    response = no_roles_authenticated.post(
        "/v1/contacts", json={"name": "Jane", "email": "jane@example.org"}
    )
    assert response.status_code == 403
