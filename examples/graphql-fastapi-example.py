import strawberry
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from typing import Optional

# Initialize Firebase
# NOTE: Before running, you must retrieve a private key from Firebase to use the Firebase SDK
# Store the private key under /Bitebook-Backend/firebase-admin-sdk/bitebook-admin-credential.json
cred = credentials.Certificate("../firebase-admin-sdk/bitebook-admin-credential.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Define User schema
@strawberry.type
class User:
    uid: Optional[str] = None
    displayName: Optional[str] = None
    profilePicture: Optional[str] = None
    createdAt: Optional[str] = None

# Define Query
@strawberry.type
class Query:
    @strawberry.field
    def getUsers(self) -> list[User]:
        users_ref = db.collection("users")
        users = users_ref.stream()

        return [
            User(
                uid=user_dict.get("uid"),
                displayName=user_dict.get("displayName"),
                profilePicture=user_dict.get("profilePicture"),
                createdAt=user_dict.get("createdAt").isoformat() if user_dict.get("createdAt") else None
            )
            for user in users
            if (user_dict := user.to_dict())
        ]

# Create Schema
schema = strawberry.Schema(Query)
graphql_app = GraphQLRouter(schema)

# FastAPI App
app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")