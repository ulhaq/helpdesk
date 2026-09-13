import pytest
from fastapi.testclient import TestClient


def test_support_site_is_created_on_first_use(admin_authenticated: TestClient) -> None:
    response = admin_authenticated.get("/v1/helpdesk/support-site")
    assert response.status_code == 200, response.text
    rs = response.json()
    assert rs["slug"].startswith("acme-corp-")
    assert rs["brand_color"] == "#293e70"
    assert rs["greeting"] is None
    assert rs["widget_enabled"] is True

    again = admin_authenticated.get("/v1/helpdesk/support-site").json()
    assert again["slug"] == rs["slug"]


def test_update_support_site(admin_authenticated: TestClient) -> None:
    response = admin_authenticated.patch(
        "/v1/helpdesk/support-site",
        json={"slug": "acme", "brand_color": "#FF0000", "greeting": "Hi there!"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["slug"] == "acme"
    assert response.json()["brand_color"] == "#ff0000"

    widget = admin_authenticated.get("/v1/widget/acme").json()
    assert widget == {
        "organization_name": "Acme Corp",
        "brand_color": "#ff0000",
        "greeting": "Hi there!",
        "help_center_enabled": True,
    }

    response = admin_authenticated.patch(
        "/v1/helpdesk/support-site", json={"greeting": None}
    )
    assert response.json()["greeting"] is None
    assert response.json()["slug"] == "acme"


def test_support_slug_is_unique(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    response = organization2_admin_authenticated.patch(
        "/v1/helpdesk/support-site", json={"slug": "globex"}
    )
    assert response.status_code == 200

    response = admin_authenticated.patch(
        "/v1/helpdesk/support-site", json={"slug": "globex"}
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "support_slug_taken"


@pytest.mark.parametrize("slug", ["ab", "Acme Corp", "-acme", "acme-", "acme_corp"])
def test_support_slug_must_be_url_safe(
    admin_authenticated: TestClient, slug: str
) -> None:
    response = admin_authenticated.patch(
        "/v1/helpdesk/support-site", json={"slug": slug}
    )
    assert response.status_code == 422


def test_support_site_requires_manage_helpdesk(
    standard_authenticated: TestClient,
) -> None:
    assert standard_authenticated.get("/v1/helpdesk/support-site").status_code == 403
    response = standard_authenticated.patch(
        "/v1/helpdesk/support-site", json={"slug": "mine"}
    )
    assert response.status_code == 403
