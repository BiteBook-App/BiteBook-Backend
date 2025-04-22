from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import Recipe, User, Ingredient, Step
from main import app

client = TestClient(app)

def test_graphql_get_recipes_by_user(client, mock_firestore_db, sample_recipe):
    mock_recipes = mock_firestore_db["recipes"]

    mock_recipe_doc = MagicMock()
    mock_recipe_doc.to_dict.return_value = sample_recipe

    mock_recipes.order_by.return_value.where.return_value.where.return_value.stream.return_value = [mock_recipe_doc]

    graphql_query = {
        "query": """
        query {
            getRecipes(userId: "user123", hasCooked: true) {
                uid
                userId
                name
                hasCooked
                createdAt
                lastUpdatedAt
            }
        }
        """
    }

    response = client.post("/graphql", json=graphql_query)
    assert response.status_code == 200

    data = response.json()["data"]["getRecipes"]
    assert len(data) == 1

    recipe = data[0]
    assert recipe["uid"] == sample_recipe["uid"]
    assert recipe["userId"] == sample_recipe["user_id"]
    assert recipe["name"] == sample_recipe["name"]
    assert recipe["hasCooked"] == sample_recipe["has_cooked"]
    assert recipe["createdAt"] == sample_recipe["createdAt"].isoformat()
    assert recipe["lastUpdatedAt"] == sample_recipe["lastUpdatedAt"].isoformat()

def test_graphql_get_home_page_recipes(client, mock_firestore_db, sample_user, sample_recipe):
    mock_users = mock_firestore_db["users"]
    mock_recipes = mock_firestore_db["recipes"]
    user_id = sample_user["uid"]

    mock_user_doc = MagicMock()
    mock_user_doc.to_dict.return_value = {
        **sample_user,
        "relationships": ["user456"]
    }
    mock_users.document.return_value.get.return_value = mock_user_doc

    mock_recipe_doc = MagicMock()
    mock_recipe_doc.id = sample_recipe["uid"]
    mock_recipe_doc.to_dict.return_value = sample_recipe

    mock_stream_query = MagicMock()
    mock_stream_query.stream.return_value = [mock_recipe_doc]

    mock_recipes.where.return_value = mock_stream_query
    mock_stream_query.where.return_value = mock_stream_query
    mock_stream_query.order_by.return_value = mock_stream_query
    mock_stream_query.limit.return_value = mock_stream_query

    with patch("main.fetch_recipe") as mock_fetch_recipe, \
         patch("main.fetch_user") as mock_fetch_user:

        mock_fetch_recipe.return_value = Recipe(
            createdAt=sample_recipe["createdAt"].isoformat(),
            lastUpdatedAt=sample_recipe["lastUpdatedAt"].isoformat(),
            user_id=sample_recipe["user_id"],
            uid=sample_recipe["uid"],
            name=sample_recipe["name"],
            url=sample_recipe["url"],
            photo_url=sample_recipe["photo_url"],
            ingredients=[Ingredient(**ing) for ing in sample_recipe["ingredients"]],
            steps=[Step(**step) for step in sample_recipe["steps"]],
            tastes=sample_recipe["tastes"],
            has_cooked=sample_recipe["has_cooked"],
            likes=sample_recipe["likes"],
            user=None
        )

        mock_fetch_user.return_value = User(
            uid=user_id,
            displayName=sample_user["displayName"],
            profilePicture=sample_user["profilePicture"],
            createdAt=sample_user["createdAt"].isoformat(),
            relationships=sample_user["relationships"]
        )

        graphql_query = {
            "query": """
            query GetHomePageRecipes($id: String!) {
                getHomePageRecipes(userId: $id) {
                    uid
                    user {
                        uid
                        displayName
                    }
                    name
                    hasCooked
                }
            }
            """,
            "variables": {
                "id": user_id
            }
        }

        response = client.post("/graphql", json=graphql_query)
        assert response.status_code == 200

        data = response.json()["data"]["getHomePageRecipes"]
        assert len(data) >= 1
        assert data[0]["uid"] == sample_recipe["uid"]
        assert data[0]["user"]["uid"] == user_id
        assert data[0]["name"] == sample_recipe["name"]
        assert data[0]["hasCooked"] is True

def test_graphql_get_taste_page_info(client, mock_firestore_db, sample_user, sample_recipe):
    user_id = sample_user["uid"]
    now = datetime.now(timezone.utc)
    sample_recipe["createdAt"] = datetime(now.year, now.month, 10, tzinfo=timezone.utc)
    sample_recipe["has_cooked"] = True

    mock_recipe_doc = MagicMock()
    mock_recipe_doc.id = sample_recipe["uid"]

    first_where_mock = MagicMock()
    second_where_mock = MagicMock()
    second_where_mock.stream.return_value = [mock_recipe_doc]
    first_where_mock.where.return_value = second_where_mock
    mock_firestore_db["recipes"].where.return_value = first_where_mock

    with patch("main.fetch_recipe") as mock_fetch_recipe, \
         patch("main.get_home_page_recipes_for_user") as mock_get_home_recipes:

        mock_fetch_recipe.return_value = MagicMock(
            createdAt=sample_recipe["createdAt"].isoformat(),
            tastes=sample_recipe["tastes"],
            has_cooked=True
        )

        mock_recipe = MagicMock()
        mock_recipe.uid = "recipe123"
        mock_recipe.name = "Test Recipe"
        mock_recipe.tastes = ["Sweet"]
        mock_get_home_recipes.return_value = [mock_recipe]

        graphql_query = {
            "query": """
            query GetTastePageInfo($id: String!) {
                getTastePageInfo(userId: $id) {
                    numRecipes
                    numTasteProfiles
                    tastePercentages {
                        taste
                        percentage
                    }
                    recommendations {
                        uid
                        name
                    }
                }
            }
            """,
            "variables": {
                "id": user_id
            }
        }

        response = client.post("/graphql", json=graphql_query)
        assert response.status_code == 200

        data = response.json()["data"]["getTastePageInfo"]

        assert data["numRecipes"] == 1
        assert data["numTasteProfiles"] == 1
        assert len(data["tastePercentages"]) == 6

        tastes = {t["taste"]: t["percentage"] for t in data["tastePercentages"]}
        assert tastes["Sweet"] == 1.0
        assert all(tastes[t] == 0.0 for t in ["Salty", "Sour", "Bitter", "Umami", "Spicy"])

        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["uid"] == "recipe123"
        assert data["recommendations"][0]["name"] == "Test Recipe"

def test_import_recipe(monkeypatch):
    mock_result = {
        "name": "Matcha Green Tea",
        "ingredients": [
            {"name": "hot water", "count": "2 ounces"},
            {"name": "steamed milk", "count": "6 ounces"}
        ],
        "instructions": [
            {"text": "Whisk the matcha.", "expanded": True},
            {"text": "Add water and mix.", "expanded": True}
        ],
        "error": False
    }

    async def mock_extract(url):
        return mock_result

    monkeypatch.setattr("main.extract", mock_extract)

    response = client.post("/import-recipe", json={"url": "https://example.com/matcha"})
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert data["name"] == "Matcha Green Tea"
    assert "ingredients" in data
    assert "instructions" in data
    assert isinstance(data["ingredients"], list)
    assert isinstance(data["instructions"], list)