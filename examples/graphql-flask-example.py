import strawberry
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from typing import Optional

# Initialize Firebase
# NOTE: Before running, you must retrieve a private key from Firebase to use the Firebase SDK
# Store the private key under /Bitebook-Backend/firebase-admin-sdk/bitebook-e7770-firebase-adminsdk-fbsvc-81ab2eb504.json
cred = credentials.Certificate("../firebase-admin-sdk/bitebook-e7770-firebase-adminsdk-fbsvc-81ab2eb504.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Define User schema
@strawberry.type
class User:
    uid: Optional[str] = None
    displayName: Optional[str] = None
    profilePicture: Optional[str] = None
    createdAt: Optional[str] = None

# Define Query to retrieve information from 'users' collection
@strawberry.type
class Query:
    @strawberry.field
    def getUsers(
        self,
        uid: Optional[bool] = True,
        displayName: Optional[bool] = True,
        profilePicture: Optional[bool] = True,
        createdAt: Optional[bool] = True
    ) -> list[User]:
        db = firestore.client()
        users_ref = db.collection("users")
        users = users_ref.stream()

        result = []
        for user in users:
            user_dict = user.to_dict()
            result.append(
                User(
                    uid=user_dict["uid"] if uid else None,
                    displayName=user_dict["displayName"] if displayName else None,
                    profilePicture=user_dict["profilePicture"] if profilePicture else None,
                    createdAt=user_dict["createdAt"].isoformat() if createdAt else None
                )
            )
        return result

# Create Schema
schema = strawberry.Schema(Query)
graphql_app = GraphQLRouter(schema)

# FastAPI App
app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")