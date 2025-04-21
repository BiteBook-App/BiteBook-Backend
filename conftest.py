import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True, scope="session")
def patch_firebase():
    with patch("firebase_admin.initialize_app") as mock_init_app, \
         patch("firebase_admin.credentials.Certificate") as mock_cert, \
         patch("firebase_admin.firestore.client") as mock_firestore_client, \
         patch("firebase_admin.storage.bucket") as mock_storage_bucket:

        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_bucket = MagicMock()
        mock_storage_bucket.return_value = mock_bucket

        mock_init_app.return_value = None
        mock_cert.return_value = MagicMock()

        yield {
            "mock_init_app": mock_init_app,
            "mock_cert": mock_cert,
            "mock_firestore_client": mock_firestore_client,
            "mock_db": mock_db,
            "mock_storage_bucket": mock_storage_bucket,
            "mock_bucket": mock_bucket,
        }

@pytest.fixture
def mock_firestore_db(patch_firebase):
    mock_db = patch_firebase["mock_db"]

    # Mock users and recipes collection
    mock_users_collection = MagicMock()
    mock_recipes_collection = MagicMock()

    def collection_side_effect(name):
        if name == "users":
            return mock_users_collection
        elif name == "recipes":
            return mock_recipes_collection
        return MagicMock()

    mock_db.collection.side_effect = collection_side_effect

    return {
        "db": mock_db,
        "users": mock_users_collection,
        "recipes": mock_recipes_collection,
    }

@pytest.fixture
def mock_storage(patch_firebase):
    mock_bucket = patch_firebase["mock_bucket"]

    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_bucket.blob.return_value = mock_blob

    return mock_blob

from datetime import datetime, timezone

@pytest.fixture
def sample_user():
    return {
        "uid": "user123",
        "displayName": "Test User",
        "profilePicture": "https://firebasestorage.googleapis.com/v0/b/bitebook-e7770.firebasestorage.app/o/images%2Fpfp.jpg?alt=media",
        "createdAt": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "relationships": ["user456"]
    }

@pytest.fixture
def sample_recipe():
    return {
        "uid": "recipe123",
        "user_id": "user123",
        "name": "Test Recipe",
        "photo_url": "https://firebasestorage.googleapis.com/v0/b/bitebook-e7770.firebasestorage.app/o/images%2Ftest.jpg?alt=media",
        "url": "https://example.com/full-recipe",
        "ingredients": [{"name": "Flour", "count": "2 cups"}],
        "steps": [{"text": "Mix ingredients", "expanded": True}],
        "tastes": ["Sweet"],
        "has_cooked": True,
        "likes": 5,
        "createdAt": datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        "lastUpdatedAt": datetime(2025, 1, 2, 8, 30, tzinfo=timezone.utc)
    }