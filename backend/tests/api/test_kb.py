from fastapi.testclient import TestClient

from src.helpdesk.enums import HelpdeskUsageMetric
from src.platform.models.billing import PlanSetting
from tests.conftest import TestSessionLocal

_FREE_PLAN_ID = 1  # seeded in conftest
_ADMIN_ID = 1


def _category(client: TestClient, name: str = "Billing", **extra: object) -> dict:
    response = client.post("/v1/kb/categories", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _article(
    client: TestClient, title: str = "How do I reset my password?", **extra: object
) -> dict:
    response = client.post(
        "/v1/kb/articles", json={"title": title, "body": "Go to **Settings**.", **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_category_slug_is_generated_and_unique(admin_authenticated: TestClient) -> None:
    assert _category(admin_authenticated, "Konto & fakturering")["slug"] == (
        "konto-fakturering"
    )
    assert _category(admin_authenticated, "Billing")["slug"] == "billing"
    assert _category(admin_authenticated, "Billing")["slug"] == "billing-2"

    response = admin_authenticated.post(
        "/v1/kb/categories", json={"name": "Payments", "slug": "billing"}
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "kb_slug_taken"


def test_categories_are_listed_in_order(admin_authenticated: TestClient) -> None:
    _category(admin_authenticated, "Second", position=2)
    _category(admin_authenticated, "First", position=1)

    response = admin_authenticated.get("/v1/kb/categories")
    assert [c["name"] for c in response.json()] == ["First", "Second"]


def test_article_lifecycle(admin_authenticated: TestClient) -> None:
    article = _article(admin_authenticated)
    assert article["slug"] == "how-do-i-reset-my-password"
    assert article["status"] == "draft"
    assert article["published_at"] is None
    assert article["author_id"] == _ADMIN_ID

    url = f"/v1/kb/articles/{article['id']}"
    published = admin_authenticated.patch(url, json={"status": "published"}).json()
    assert published["published_at"] is not None

    # Unpublishing keeps the original publication date.
    draft = admin_authenticated.patch(url, json={"status": "draft"}).json()
    assert draft["published_at"] == published["published_at"]

    listing = admin_authenticated.get("/v1/kb/articles?status__eq=draft").json()
    assert [a["id"] for a in listing["items"]] == [article["id"]]
    assert "body" not in listing["items"][0]

    assert admin_authenticated.delete(url).status_code == 204
    assert admin_authenticated.get(url).status_code == 404


def test_article_slugs(admin_authenticated: TestClient) -> None:
    assert _article(admin_authenticated, "Sådan ændrer du din adgangskode")["slug"] == (
        "saadan-aendrer-du-din-adgangskode"
    )
    first = _article(admin_authenticated, "Reset")
    second = _article(admin_authenticated, "Reset")
    assert second["slug"] == "reset-2"

    response = admin_authenticated.patch(
        f"/v1/kb/articles/{second['id']}", json={"slug": first["slug"]}
    )
    assert response.status_code == 409

    # A deleted article's slug becomes available again.
    admin_authenticated.delete(f"/v1/kb/articles/{first['id']}")
    response = admin_authenticated.patch(
        f"/v1/kb/articles/{second['id']}", json={"slug": "reset"}
    )
    assert response.status_code == 200


def test_article_category(admin_authenticated: TestClient) -> None:
    category = _category(admin_authenticated)
    article = _article(admin_authenticated, category_id=category["id"])
    assert article["category"] == {
        "id": category["id"],
        "name": "Billing",
        "slug": "billing",
    }

    url = f"/v1/kb/articles/{article['id']}"
    rs = admin_authenticated.patch(url, json={"category_id": None}).json()
    assert rs["category_id"] is None
    assert rs["category"] is None


def test_deleting_a_category_keeps_its_articles(
    admin_authenticated: TestClient,
) -> None:
    category = _category(admin_authenticated)
    article = _article(admin_authenticated, category_id=category["id"])

    response = admin_authenticated.delete(f"/v1/kb/categories/{category['id']}")
    assert response.status_code == 204

    rs = admin_authenticated.get(f"/v1/kb/articles/{article['id']}").json()
    assert rs["category_id"] is None


def test_article_category_must_belong_to_organization(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    other = _category(organization2_admin_authenticated)

    response = admin_authenticated.post(
        "/v1/kb/articles", json={"title": "Hi", "category_id": other["id"]}
    )
    assert response.status_code == 404


def test_articles_are_isolated_between_organizations(
    admin_authenticated: TestClient, organization2_admin_authenticated: TestClient
) -> None:
    article = _article(admin_authenticated)

    client = organization2_admin_authenticated
    assert client.get(f"/v1/kb/articles/{article['id']}").status_code == 404
    assert client.get("/v1/kb/articles").json()["total"] == 0


def test_preview_cannot_inject_markup(admin_authenticated: TestClient) -> None:
    response = admin_authenticated.post(
        "/v1/kb/articles/preview",
        json={
            "body": "<script>alert(1)</script>\n\n"
            "[click](javascript:alert(1)) and **bold**"
        },
    )
    assert response.status_code == 200
    html = response.json()["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert 'href="javascript' not in html
    assert "<strong>bold</strong>" in html


async def test_article_capacity_limit(admin_authenticated: TestClient) -> None:
    async with TestSessionLocal() as session:
        session.add(
            PlanSetting(
                plan_id=_FREE_PLAN_ID, key=HelpdeskUsageMetric.KB_ARTICLES, value=1
            )
        )
        await session.commit()

    _article(admin_authenticated)
    response = admin_authenticated.post("/v1/kb/articles", json={"title": "Second"})
    assert response.status_code == 402
    assert response.json()["error_code"] == "capacity_exceeded"


def test_kb_requires_manage_kb(standard_authenticated: TestClient) -> None:
    assert standard_authenticated.get("/v1/kb/articles").status_code == 403
    response = standard_authenticated.post("/v1/kb/categories", json={"name": "X"})
    assert response.status_code == 403
