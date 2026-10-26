from fastapi import FastAPI
import strawberry
from strawberry.fastapi import GraphQLRouter

# 1. Type User
@strawberry.type
class User:
    id: int
    name: str
    email: str

# 2. Définition de la Query
@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "hello from GraphQL!"
    
    @strawberry.field
    def user(self) -> User:
        return User(id=1, name="Alice", email="alice@example.com")

# 3. Définition de la Mutation
@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, name: str, email: str) -> User:
        # --- Validation (Best Practice n°2) ---
        if len(name) < 3:
            # Cela renverra une erreur formatée dans le JSON de réponse
            raise ValueError("Le nom est trop court (min 3 caractères) !")
            
        if "@" not in email:
            raise ValueError("L'email n'est pas valide !")
    
        # --- Logique ---
        # Si tout est bon, on continue
        print(f"Sauvegarde de {name}...")
        return User(id=2, name=name, email=email)

# 4. Création du Schéma
schema = strawberry.Schema(query=Query, mutation=Mutation)

# 5. Application FastAPI
app = FastAPI()
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")