from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import main

def test_graphql_create_recipe(client, mock_firestore_db):
    mock_recipes = mock_firestore_db["recipes"]

    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "recipe123"
    mock_recipes.document.return_value = mock_doc_ref

    created_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    with patch("main.datetime") as mock_datetime:
        mock_datetime.now.return_value = created_at
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

        graphql_query = {
            "query": """
            mutation CreateRecipe($input: RecipeInput!) {
                createRecipe(recipeData: $input) {
                    uid
                    userId
                    name
                    createdAt
                    lastUpdatedAt
                }
            }
            """,
            "variables": {
                "input": {
                    "userId": "user123",
                    "name": "Chocolate Cake",
                    "url": "https://example.com/choco-cake",
                    "photoUrl": "https://example.com/photo.jpg",
                    "ingredients": [{"name": "Flour", "count": "2 cups"}],
                    "steps": [{"text": "Mix ingredients", "expanded": True}],
                    "tastes": ["Sweet"],
                    "hasCooked": True
                }
            }
        }

        response = client.post("/graphql", json=graphql_query)
        assert response.status_code == 200

        data = response.json()["data"]["createRecipe"]
        assert data["uid"] == "recipe123"
        assert data["userId"] == "user123"
        assert data["name"] == "Chocolate Cake"
        assert data["createdAt"] == created_at.isoformat()
        assert data["lastUpdatedAt"] is None

        mock_doc_ref.set.assert_called_once_with({
            "user_id": "user123",
            "uid": "recipe123",
            "url": "https://example.com/choco-cake",
            "name": "Chocolate Cake",
            "photo_url": "https://example.com/photo.jpg",
            "ingredients": [{"name": "Flour", "count": "2 cups"}],
            "steps": [{"text": "Mix ingredients", "expanded": True}],
            "tastes": ["Sweet"],
            "has_cooked": True,
            "likes": 0,
            "createdAt": created_at
        })

def test_graphql_edit_recipe(client, mock_firestore_db, sample_recipe):
    mock_recipes = mock_firestore_db["recipes"]

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value.exists = True
    mock_doc_ref.get.return_value.to_dict.return_value = {
        **sample_recipe,
        "name": "Updated Cake",
        "lastUpdatedAt": datetime(2023, 2, 1, 10, 30, 0, tzinfo=timezone.utc)
    }
    mock_recipes.document.return_value = mock_doc_ref

    updated_at = datetime(2023, 2, 1, 10, 30, 0, tzinfo=timezone.utc)

    with patch.object(main, "datetime") as mock_datetime:
        mock_datetime.now.return_value = updated_at
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

        graphql_query = {
            "query": """
            mutation EditRecipe($id: String!, $data: RecipeInput!) {
                editRecipe(recipeId: $id, recipeData: $data) {
                    uid
                    userId
                    name
                    createdAt
                    lastUpdatedAt
                }
            }
            """,
            "variables": {
                "id": sample_recipe["uid"],
                "data": {
                    "name": "Updated Cake"
                }
            }
        }

        response = client.post("/graphql", json=graphql_query)
        assert response.status_code == 200

        data = response.json()["data"]["editRecipe"]
        assert data["uid"] == sample_recipe["uid"]
        assert data["userId"] == sample_recipe["user_id"]
        assert data["name"] == "Updated Cake"
        assert data["createdAt"] == sample_recipe["createdAt"].isoformat()
        assert data["lastUpdatedAt"] == updated_at.isoformat()

        mock_doc_ref.update.assert_called_once_with({
            "name": "Updated Cake",
            "lastUpdatedAt": updated_at
        })

def test_graphql_delete_recipe(client, mock_firestore_db, mock_storage, sample_recipe):
    mock_recipes = mock_firestore_db["recipes"]
    mock_blob = mock_storage

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value.exists = True
    mock_doc_ref.get.return_value.to_dict.return_value = sample_recipe
    mock_recipes.document.return_value = mock_doc_ref

    mock_blob.exists.return_value = True

    graphql_query = {
        "query": """
        mutation DeleteRecipe($id: String!) {
            deleteRecipe(recipeId: $id)
        }
        """,
        "variables": {
            "id": sample_recipe["uid"]
        }
    }

    response = client.post("/graphql", json=graphql_query)
    assert response.status_code == 200
    assert response.json()["data"]["deleteRecipe"] is None

    mock_doc_ref.delete.assert_called_once()
    mock_blob.delete.assert_called_once()

def test_graphql_edit_user(client, mock_firestore_db, sample_user):
    mock_users = mock_firestore_db["users"]
    user_id = sample_user["uid"]

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value.exists = True
    mock_doc_ref.get.return_value.to_dict.return_value = sample_user
    mock_users.document.return_value = mock_doc_ref

    mock_users.where.return_value.get.return_value = []

    updated_user_data = {
        **sample_user,
        "displayName": "New Name",
        "profilePicture": "https://example.com/new.jpg"
    }
    mock_doc_ref.get.return_value.to_dict.return_value = updated_user_data

    graphql_query = {
        "query": """
        mutation EditUser($id: String!, $name: String!, $pic: String!) {
            editUser(userId: $id, displayName: $name, profilePicture: $pic) {
                uid
                displayName
                profilePicture
                createdAt
            }
        }
        """,
        "variables": {
            "id": user_id,
            "name": "New Name",
            "pic": "https://example.com/new.jpg"
        }
    }

    response = client.post("/graphql", json=graphql_query)
    assert response.status_code == 200

    data = response.json()["data"]["editUser"]
    assert data["uid"] == user_id
    assert data["displayName"] == "New Name"
    assert data["profilePicture"] == "https://example.com/new.jpg"
    assert data["createdAt"] == sample_user["createdAt"].isoformat()

    mock_doc_ref.update.assert_any_call({"displayName": "New Name"})
    mock_doc_ref.update.assert_any_call({"profilePicture": "https://example.com/new.jpg"})

def test_graphql_edit_user(client, mock_firestore_db, sample_user):
    mock_users = mock_firestore_db["users"]
    user_id = sample_user["uid"]

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value.exists = True
    mock_doc_ref.get.return_value.to_dict.return_value = sample_user
    mock_users.document.return_value = mock_doc_ref

    mock_users.where.return_value.get.return_value = []

    updated_user_data = {
        **sample_user,
        "displayName": "New Name",
        "profilePicture": "https://firebasestorage.googleapis.com/v0/b/bitebook-e7770.firebasestorage.app/o/images%2Fnewpfp.jpg?alt=media"
    }
    mock_doc_ref.get.return_value.to_dict.return_value = updated_user_data

    graphql_query = {
        "query": """
        mutation EditUser($id: String!, $name: String!, $pic: String!) {
            editUser(userId: $id, displayName: $name, profilePicture: $pic) {
                uid
                displayName
                profilePicture
                createdAt
            }
        }
        """,
        "variables": {
            "id": user_id,
            "name": "New Name",
            "pic": "https://firebasestorage.googleapis.com/v0/b/bitebook-e7770.firebasestorage.app/o/images%2Fnewpfp.jpg?alt=media"
        }
    }

    response = client.post("/graphql", json=graphql_query)
    assert response.status_code == 200

    data = response.json()["data"]["editUser"]
    assert data["uid"] == user_id
    assert data["displayName"] == "New Name"
    assert data["profilePicture"] == updated_user_data["profilePicture"]
    assert data["createdAt"] == sample_user["createdAt"].isoformat()

    mock_doc_ref.update.assert_any_call({"displayName": "New Name"})
    mock_doc_ref.update.assert_any_call({"profilePicture": updated_user_data["profilePicture"]})

def test_graphql_create_relationship(client, mock_firestore_db, sample_user):
    mock_users = mock_firestore_db["users"]

    user1_id = sample_user["uid"]
    user2_id = "user456"

    mock_user1_ref = MagicMock()
    mock_user2_ref = MagicMock()

    # Simulate Firestore .get().to_dict()
    mock_user1_ref.get.return_value.to_dict.return_value = {
        **sample_user,
        "uid": user1_id,
        "relationships": []
    }

    mock_user2_ref.get.return_value.to_dict.return_value = {
        "uid": user2_id,
        "relationships": []
    }

    mock_users.document.side_effect = lambda uid: {
        user1_id: mock_user1_ref,
        user2_id: mock_user2_ref
    }[uid]

    graphql_mutation = {
        "query": """
        mutation CreateRelationship($data: RelationshipInput!) {
            createRelationship(relationshipData: $data)
        }
        """,
        "variables": {
            "data": {
                "firstUserId": user1_id,
                "secondUserId": user2_id
            }
        }
    }

    response = client.post("/graphql", json=graphql_mutation)
    assert response.status_code == 200
    assert "errors" not in response.json()

    mock_user1_ref.update.assert_called_once_with({
        "relationships": [user2_id]
    })

    mock_user2_ref.update.assert_called_once_with({
        "relationships": [user1_id]
    })