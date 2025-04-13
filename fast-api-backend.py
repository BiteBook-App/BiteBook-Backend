import strawberry
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional
from datetime import datetime, timezone
from summarize import extract
from pydantic import BaseModel
from google.cloud.firestore_v1.base_query import FieldFilter

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
    relationships: Optional[List[str]] = None

# Define the Recipe schema (output type for queries)
@strawberry.type
class Ingredient:
    name: str
    count: str

@strawberry.type
class Step:
    text: str
    expanded: bool

@strawberry.type
class Recipe:
    user_id: Optional[str]
    uid: Optional[str]
    url: Optional[str]
    name: Optional[str]
    photo_url: Optional[str]
    ingredients: Optional[List[Ingredient]]
    steps: Optional[List[Step]]
    tastes: Optional[List[str]]
    has_cooked: Optional[bool]
    likes: Optional[int]
    createdAt: Optional[str]
    lastUpdatedAt: Optional[str]
    user: Optional[User] = None

@strawberry.type
class Relationship:
    user_ids: Optional[List[str]]
    createdAt: Optional[str]

# ---------- MUTATION CLASSES ----------

# Define the Recipe schema (input type for creating a recipe)
@strawberry.input
class IngredientInput:
    name: str
    count: str

@strawberry.input
class StepInput:
    text: str
    expanded: bool

@strawberry.input
class RecipeInput:
    user_id: Optional[str] = None
    url: Optional[str] = None
    name: Optional[str] = None
    photo_url: Optional[str] = None
    ingredients: Optional[List[IngredientInput]] = None
    steps: Optional[List[StepInput]] = None
    tastes: Optional[List[str]] = None
    has_cooked: Optional[bool] = None

@strawberry.input
class RelationshipInput:
    first_user_id: str
    second_user_id: str

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
                        createdAt=user_dict.get("createdAt").isoformat() if user_dict.get("createdAt") else None,
                        relationships=user_dict.get("relationships", [])
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
                createdAt=user_dict.get("createdAt").isoformat() if user_dict.get("createdAt") else None,
                relationships=user_dict.get("relationships", [])
            )
            for user in users
            if (user_dict := user.to_dict())
        ]
    
    @strawberry.field
    def get_recipes(self, user_id: Optional[str] = None, has_cooked: Optional[bool] = None) -> list[Recipe]:
        recipes_ref = db.collection("recipes").order_by("createdAt", direction="DESCENDING")
        
        # If user_id is provided, filter results
        if user_id:
            recipes_ref = recipes_ref.where("user_id", "==", user_id)
        if has_cooked is not None:
            recipes_ref = recipes_ref.where("has_cooked", "==", has_cooked)

        recipes = recipes_ref.stream()
        recipe_list = [
            Recipe(
                user_id=recipe_dict.get("user_id"),
                uid=recipe_dict.get("uid"),
                url=recipe_dict.get("url"),
                name=recipe_dict.get("name"),
                photo_url=recipe_dict.get("photo_url"),
                ingredients=recipe_dict.get("ingredients", []),
                steps=recipe_dict.get("steps", []),
                tastes=recipe_dict.get("tastes", []),
                has_cooked=recipe_dict.get("has_cooked"),
                likes=recipe_dict.get("likes", 0),
                createdAt=recipe_dict.get("createdAt").isoformat() if recipe_dict.get("createdAt") else None,
                lastUpdatedAt=recipe_dict.get("lastUpdatedAt").isoformat() if recipe_dict.get("lastUpdatedAt") else None
            )
            for recipe in recipes
            if (recipe_dict := recipe.to_dict())
        ]

        # Sort recipes by the latest of createdAt and lastUpdatedAt (most recent first)
        recipe_list.sort(
            key=lambda r: max(
                [dt for dt in [
                    datetime.fromisoformat(r.createdAt) if r.createdAt else None,
                    datetime.fromisoformat(r.lastUpdatedAt) if r.lastUpdatedAt else None
                ] if dt is not None]
            ),
            reverse=True
        )

        return recipe_list

    @strawberry.field
    def get_recipe(self, recipe_uid: str) -> Recipe:
        recipe = fetch_recipe(recipe_uid)
        recipe.user = fetch_user(recipe.user_id)
        return recipe
    
    @strawberry.field
    def getHomePageRecipes(self, user_id: Optional[str] = None, num_recipes: Optional[int] = 10) -> List[Recipe]:
        if not user_id:
            return []
        
        # Step 1: Get the user's relationships field
        user_ref = db.collection("users").document(user_id)
        user_ref_doc = user_ref.get().to_dict()

        # Get current relationships or empty list if none
        relationships = user_ref_doc.get("relationships", [])
        relationships.append(user_id)  # Include user's own recipes

        # Step 2: Fetch recipes for each relationship
        home_page_recipes = []
        for friend_id in relationships:
            recipes_query = db.collection("recipes") \
                .where("user_id", "==", friend_id) \
                .where("has_cooked", "==", True) \
                .order_by("createdAt", direction=firestore.Query.DESCENDING) \
                .limit(num_recipes)

            recipe_docs = recipes_query.stream()
            for doc in recipe_docs:
                recipe = fetch_recipe(doc.id)
                if recipe:
                    recipe.user = fetch_user(recipe.user_id)
                    home_page_recipes.append(recipe)

        # Step 3: Sort recipes by the latest of createdAt or lastUpdatedAt
        def get_latest_datetime(recipe):
            dates = []
            if recipe.createdAt:
                dates.append(datetime.fromisoformat(recipe.createdAt))
            if recipe.lastUpdatedAt:
                dates.append(datetime.fromisoformat(recipe.lastUpdatedAt))
            return max(dates) if dates else datetime.min

        home_page_recipes.sort(key=get_latest_datetime, reverse=True)

        # Step 4: Return top N recipes
        return home_page_recipes[:num_recipes]

# ---------- MUTATIONS ----------
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_recipe(self, recipe_data: RecipeInput) -> Recipe:
        # Create a new document reference without specifying an ID (Firestore will auto-generate it)
        recipe_ref = db.collection("recipes").document()
        recipe_id = recipe_ref.id  # Get the auto-generated ID
        
        # Convert `IngredientInput` and `StepInput` objects into dictionaries
        ingredients_list = [{"name": ing.name, "count": ing.count} for ing in (recipe_data.ingredients or [])]
        steps_list = [{"text": step.text, "expanded": step.expanded} for step in (recipe_data.steps or [])]
        
        # Construct the Firestore document
        recipe_doc = {
            "user_id": recipe_data.user_id,
            "uid": recipe_id,  # Store the Firestore-generated ID
            "url": recipe_data.url,
            "name": recipe_data.name,
            "photo_url": recipe_data.photo_url,
            "ingredients": ingredients_list,  # Store as list of dictionaries
            "steps": steps_list,  # Store as list of dictionaries
            "tastes": recipe_data.tastes or [],
            "has_cooked": recipe_data.has_cooked,
            "likes": 0,  # Default to 0 likes
            "createdAt": datetime.now(timezone.utc)  # Timestamp
        }

        # Set the document with the generated ID
        recipe_ref.set(recipe_doc)

        return Recipe(
            user_id=recipe_data.user_id,
            uid=recipe_id,
            url=recipe_data.url,
            name=recipe_data.name,
            photo_url=recipe_data.photo_url,
            ingredients=ingredients_list,  # Return as list of dictionaries
            steps=steps_list,  # Return as list of dictionaries
            tastes=recipe_data.tastes or [],
            has_cooked=recipe_data.has_cooked,
            likes=0,
            createdAt=recipe_doc["createdAt"].isoformat(),
            lastUpdatedAt=None
        )

    @strawberry.mutation
    def edit_recipe(self, recipe_id: str, recipe_data: RecipeInput) -> Recipe:
        # Get reference to the existing recipe document
        recipe_ref = db.collection("recipes").document(recipe_id)
        recipe_doc = recipe_ref.get()

        # Check if the recipe exists
        if not recipe_doc.exists:
            raise ValueError(f"Recipe with ID {recipe_id} not found")

        # Convert IngredientInput and StepInput objects into dictionaries
        ingredients_list = [{"name": ing.name, "count": ing.count} for ing in (recipe_data.ingredients or [])]
        steps_list = [{"text": step.text, "expanded": step.expanded} for step in (recipe_data.steps or [])]

        # Create an update dictionary with only the fields that are provided
        update_data = {}

        if recipe_data.user_id is not None:
            update_data["user_id"] = recipe_data.user_id
        if recipe_data.url is not None:
            update_data["url"] = recipe_data.url
        if recipe_data.name is not None:
            update_data["name"] = recipe_data.name
        if recipe_data.has_cooked is not None:
            update_data["has_cooked"] = recipe_data.has_cooked
        if recipe_data.photo_url is not None:
            update_data["photo_url"] = recipe_data.photo_url
        if recipe_data.ingredients is not None:
            update_data["ingredients"] = ingredients_list
        if recipe_data.steps is not None:
            update_data["steps"] = steps_list
        if recipe_data.tastes is not None:
            update_data["tastes"] = recipe_data.tastes

        # Add a lastUpdatedAt timestamp
        update_data["lastUpdatedAt"] = datetime.now(timezone.utc)

        # Update the document with new values
        recipe_ref.update(update_data)

        # Get the updated recipe
        updated_recipe = recipe_ref.get().to_dict()

        # Return the updated Recipe object
        return Recipe(
            user_id=updated_recipe.get("user_id"),
            uid=updated_recipe.get("uid"),
            url=updated_recipe.get("url"),
            name=updated_recipe.get("name"),
            has_cooked=updated_recipe.get("has_cooked"),
            photo_url=updated_recipe.get("photo_url"),
            ingredients=updated_recipe.get("ingredients", []),
            steps=updated_recipe.get("steps", []),
            tastes=updated_recipe.get("tastes", []),
            likes=updated_recipe.get("likes", 0),
            createdAt=updated_recipe.get("createdAt").isoformat() if updated_recipe.get("createdAt") else None,
            lastUpdatedAt=updated_recipe.get("lastUpdatedAt").isoformat() if updated_recipe.get("lastUpdatedAt") else None
        )

    @strawberry.mutation
    def toggle_recipe_like(self, recipe_id: str, user_id: str) -> Recipe:
        # Get reference to the recipe document
        recipe_ref = db.collection("recipes").document(recipe_id)
        recipe_doc = recipe_ref.get()

        # Check if the recipe exists
        if not recipe_doc.exists:
            raise ValueError(f"Recipe with ID {recipe_id} not found")

        # Get the existing recipe data
        recipe_data = recipe_doc.to_dict()

        # Check if we have a likes_by_user field, if not create it
        if "likes_by_user" not in recipe_data:
            recipe_data["likes_by_user"] = []

        # Get current likes count
        current_likes = recipe_data.get("likes", 0)

        # Check if user has already liked this recipe
        if user_id in recipe_data["likes_by_user"]:
            # User already liked, so remove the like
            recipe_data["likes_by_user"].remove(user_id)
            new_likes = max(0, current_likes - 1)  # Ensure likes don't go below 0
        else:
            # User hasn't liked, so add the like
            recipe_data["likes_by_user"].append(user_id)
            new_likes = current_likes + 1

        # Update the likes count
        recipe_data["likes"] = new_likes

        # Update the document in Firestore
        recipe_ref.update({
            "likes": new_likes,
            "likes_by_user": recipe_data["likes_by_user"],
            "lastUpdatedAt": datetime.now(timezone.utc)
        })

        # Return the updated Recipe object
        return Recipe(
            user_id=recipe_data.get("user_id"),
            uid=recipe_data.get("uid"),
            url=recipe_data.get("url"),
            name=recipe_data.get("name"),
            photo_url=recipe_data.get("photo_url"),
            ingredients=recipe_data.get("ingredients", []),
            steps=recipe_data.get("steps", []),
            tastes=recipe_data.get("tastes", []),
            likes=new_likes,
            createdAt=recipe_data.get("createdAt").isoformat() if recipe_data.get("createdAt") else None
        )
    
    @strawberry.mutation
    def edit_user(self, user_id: str, display_name: Optional[str] = None, profile_picture: Optional[str] = None) -> User:
        # Get reference to the existing user document
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()

        # Check if the recipe exists
        if not user_doc.exists:
            raise ValueError(f"User with ID {user_id} not found")
        
        # Check if the display name is already taken (excluding the current user)
        if display_name:
            users_with_same_name = db.collection("users").where("displayName", "==", display_name).get()
            
            for user in users_with_same_name:
                if user.id != user_id:  # Ensure it's not the same user updating their own name
                    raise ValueError(f"Display name '{display_name}' is already taken.")
        
        if display_name is not None: 
            user_ref.update({
                "displayName": display_name,
            })
        if profile_picture is not None:
            user_ref.update({
                "profilePicture": profile_picture
            })

        # Fetch the updated user document
        updated_user_doc = user_ref.get()
        user_data = updated_user_doc.to_dict()

        # Return updated User object
        return User(
            uid=user_id,
            displayName=user_data.get("displayName"),
            profilePicture=user_data.get("profilePicture"),
            createdAt=user_data.get("createdAt").isoformat() if user_data.get("createdAt") else None
        )
    
    @strawberry.mutation
    def create_relationship(self, relationship_data: RelationshipInput) -> None:
        # Update users' relationships list
        first_user_ref = db.collection("users").document(relationship_data.first_user_id)
        second_user_ref = db.collection("users").document(relationship_data.second_user_id)

        first_user_doc = first_user_ref.get().to_dict()
        second_user_doc = second_user_ref.get().to_dict()

        # Get current relationships or empty list if none
        first_user_relationships = first_user_doc.get("relationships", [])
        second_user_relationships = second_user_doc.get("relationships", [])

        # Avoid duplicates
        if relationship_data.second_user_id not in first_user_relationships:
            first_user_relationships.append(relationship_data.second_user_id)
        if relationship_data.first_user_id not in second_user_relationships:
            second_user_relationships.append(relationship_data.first_user_id)

        # Update Firestore
        first_user_ref.update({"relationships": first_user_relationships})
        second_user_ref.update({"relationships": second_user_relationships})

        return
    
# HELPER FUNCTIONS
def fetch_recipe(recipe_uid: str) -> Optional[Recipe]:
    recipe_ref = db.collection("recipes").document(recipe_uid)
    recipe_doc = recipe_ref.get()

    if not recipe_doc.exists:
        return None

    recipe_dict = recipe_doc.to_dict()

    return Recipe(
        user_id=recipe_dict.get("user_id"),
        uid=recipe_dict.get("uid"),
        url=recipe_dict.get("url"),
        name=recipe_dict.get("name"),
        photo_url=recipe_dict.get("photo_url"),
        ingredients=[Ingredient(name=ing["name"], count=ing["count"]) for ing in recipe_dict.get("ingredients", [])],
        steps=[Step(text=step["text"], expanded=step["expanded"]) for step in recipe_dict.get("steps", [])],
        tastes=recipe_dict.get("tastes", []),
        has_cooked=recipe_dict.get("has_cooked"),
        likes=recipe_dict.get("likes", 0),
        createdAt=recipe_dict.get("createdAt").isoformat() if recipe_dict.get("createdAt") else None,
        lastUpdatedAt=recipe_dict.get("lastUpdatedAt").isoformat() if recipe_dict.get("lastUpdatedAt") else None
    )

def fetch_user(user_id: str) -> Optional[User]:
        users_ref = db.collection("users")
        if user_id:
            user_doc = users_ref.document(user_id).get()
            if user_doc.exists:
                user_dict = user_doc.to_dict()
                return User(
                        uid=user_dict.get("uid"),
                        displayName=user_dict.get("displayName"),
                        profilePicture=user_dict.get("profilePicture"),
                        createdAt=user_dict.get("createdAt").isoformat() if user_dict.get("createdAt") else None
                    )

schema = strawberry.Schema(query=Query, mutation=Mutation)

# FastAPI App
graphql_app = GraphQLRouter(schema)
app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")

# Define request body model
class URLRequest(BaseModel):
    url: str

@app.post("/import-recipe")
async def root(data: URLRequest):
    return await extract(data.url)