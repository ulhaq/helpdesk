import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def slug(admin_authenticated: TestClient) -> str:
    return admin_authenticated.get("/v1/helpdesk/support-site").json()["slug"]


def _article(
    client: TestClient,
    title: str,
    *,
    body: str = "Body",
    status: str = "published",
    category_id: int | None = None,
) -> dict:
    response = client.post(
        "/v1/kb/articles",
        json={
            "title": title,
            "body": body,
            "status": status,
            "category_id": category_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _category(client: TestClient, name: str) -> dict:
    response = client.post("/v1/kb/categories", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_home_shows_only_published_content(
    admin_authenticated: TestClient, slug: str
) -> None:
    billing = _category(admin_authenticated, "Billing")
    _category(admin_authenticated, "Nothing published yet")
    _article(
        admin_authenticated,
        "Update your card",
        body="Open **Billing** and choose a new card.",
        category_id=billing["id"],
    )
    _article(
        admin_authenticated, "Secret draft", status="draft", category_id=billing["id"]
    )

    response = admin_authenticated.get(f"/v1/help/{slug}")
    assert response.status_code == 200
    rs = response.json()
    assert rs["organization_name"] == "Acme Corp"
    assert rs["categories"] == [
        {"name": "Billing", "slug": "billing", "description": None, "article_count": 1}
    ]
    assert [a["title"] for a in rs["recent_articles"]] == ["Update your card"]
    assert rs["recent_articles"][0]["excerpt"] == "Open Billing and choose a new card."


def test_search_help_articles(admin_authenticated: TestClient, slug: str) -> None:
    billing = _category(admin_authenticated, "Billing")
    _article(admin_authenticated, "Reset your password", body="Use the reset link.")
    _article(admin_authenticated, "Invoices", category_id=billing["id"])
    _article(admin_authenticated, "Password policy", status="draft")

    response = admin_authenticated.get(f"/v1/help/{slug}/articles?q=password")
    assert [a["title"] for a in response.json()["articles"]] == ["Reset your password"]

    response = admin_authenticated.get(f"/v1/help/{slug}/articles?category=billing")
    assert response.json()["category"] == {"name": "Billing", "slug": "billing"}
    assert [a["title"] for a in response.json()["articles"]] == ["Invoices"]

    response = admin_authenticated.get(f"/v1/help/{slug}/articles?category=nope")
    assert response.status_code == 404


def test_read_an_article(admin_authenticated: TestClient, slug: str) -> None:
    article = _article(
        admin_authenticated,
        "Change your plan",
        body="## Steps\n\n1. Open **Settings**\n2. <b>Pick</b> a plan",
    )

    response = admin_authenticated.get(f"/v1/help/{slug}/articles/{article['slug']}")
    assert response.status_code == 200
    html = response.json()["html"]
    assert "<h2>Steps</h2>" in html
    assert "<strong>Settings</strong>" in html
    assert "&lt;b&gt;Pick&lt;/b&gt;" in html


def test_draft_articles_are_not_public(
    admin_authenticated: TestClient, slug: str
) -> None:
    draft = _article(admin_authenticated, "Coming soon", status="draft")

    response = admin_authenticated.get(f"/v1/help/{slug}/articles/{draft['slug']}")
    assert response.status_code == 404


def test_disabled_help_center_is_unavailable(
    admin_authenticated: TestClient, slug: str
) -> None:
    admin_authenticated.patch(
        "/v1/helpdesk/support-site", json={"help_center_enabled": False}
    )
    assert admin_authenticated.get(f"/v1/help/{slug}").status_code == 404
    # The widget stays available and stops offering article search.
    widget = admin_authenticated.get(f"/v1/widget/{slug}").json()
    assert widget["help_center_enabled"] is False


def test_help_center_only_shows_its_organization(
    slug: str, organization2_admin_authenticated: TestClient
) -> None:
    other = _article(organization2_admin_authenticated, "Globex only")

    response = organization2_admin_authenticated.get(
        f"/v1/help/{slug}/articles/{other['slug']}"
    )
    assert response.status_code == 404


def test_unknown_help_center(client: TestClient) -> None:
    assert client.get("/v1/help/no-such-site").status_code == 404
