import strawberry
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional
from datetime import datetime, timezone

# Initialize Firebase
cred = credentials.Certificate("./firebase-admin-sdk/bitebook-admin-credential.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------- QUERY CLASSES ----------

# Define User schema
@strawberry.type
class User:
    uid: Optional[str] = None
    displayName: Optional[str] = None
    profilePicture: Optional[str] = None
    createdAt: Optional[str] = None

# Define the Recipe schema (output type for queries)
@strawberry.type
class Recipe:
    user_id: Optional[str]
    uid: Optional[str]
    url: Optional[str]
    name: Optional[str]
    photo_url: Optional[str]
    ingredients: Optional[List[str]]
    steps: Optional[List[str]]
    tastes: Optional[List[str]]
    likes: Optional[int]
    createdAt: Optional[str]

# ---------- MUTATION CLASSES ----------

# Define the Recipe schema (input type for creating a recipe)
@strawberry.input
class RecipeInput:
    user_id: Optional[str] = None
    url: Optional[str] = None
    name: Optional[str] = None
    photo_url: Optional[str] = None
    ingredients: Optional[List[str]] = None
    steps: Optional[List[str]] = None
    tastes: Optional[List[str]] = None

# ---------- QUERIES ----------
@strawberry.type
class Query:
    @strawberry.field
    def getUsers(self, uid: Optional[str] = None) -> List[User]:
        users_ref = db.collection("users")

        # If uid is provided, filter by uid
        if uid:
            user_doc = users_ref.document(uid).get()
            if user_doc.exists:
                user_dict = user_doc.to_dict()
                return [
                    User(
                        uid=user_dict.get("uid"),
                        displayName=user_dict.get("displayName"),
                        profilePicture=user_dict.get("profilePicture"),
                        createdAt=user_dict.get("createdAt").isoformat() if user_dict.get("createdAt") else None
                    )
                ]
            return []  # Return an empty list if the user does not exist

        # Otherwise, return all users
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
    
    @strawberry.field
    def get_recipes(self, user_id: Optional[str] = None) -> list[Recipe]:
        recipes_ref = db.collection("recipes")
        
        # If user_id is provided, filter results
        if user_id:
            recipes_ref = recipes_ref.where("user_id", "==", user_id)

        recipes = recipes_ref.stream()
        return [
            Recipe(
                user_id=recipe_dict.get("user_id"),
                uid=recipe_dict.get("uid"),
                url=recipe_dict.get("url"),
                name=recipe_dict.get("name"),
                photo_url=recipe_dict.get("photo_url"),
                ingredients=recipe_dict.get("ingredients", []),
                steps=recipe_dict.get("steps", []),
                tastes=recipe_dict.get("tastes", []),
                likes=recipe_dict.get("likes", 0),
                createdAt=recipe_dict.get("createdAt").isoformat() if recipe_dict.get("createdAt") else None
            )
            for recipe in recipes
            if (recipe_dict := recipe.to_dict())
        ]

# ---------- MUTATIONS ----------
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_recipe(self, recipe_data: RecipeInput) -> Recipe:
        # Create a new document reference without specifying an ID (Firestore will auto-generate it)
        recipe_ref = db.collection("recipes").document()
        recipe_id = recipe_ref.id  # Get the auto-generated ID
        
        recipe_doc = {
            "user_id": recipe_data.user_id,
            "uid": recipe_id,  # Store the Firestore-generated ID
            "url": recipe_data.url,
            "name": recipe_data.name,
            "photo_url": recipe_data.photo_url,
            "ingredients": recipe_data.ingredients or [],
            "steps": recipe_data.steps or [],
            "tastes": recipe_data.tastes or [],
            "likes": 0,  # Default to 0 likes
            "createdAt": datetime.now(timezone.utc)  # Timestamp
        }

        # Set the document with the generated ID
        recipe_ref.set(recipe_doc)

        return Recipe(**recipe_doc)

schema = strawberry.Schema(query=Query, mutation=Mutation)

# FastAPI App
graphql_app = GraphQLRouter(schema)
app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")