from fastapi import FastAPI
import strawberry
from strawberry.fastapi import GraphQLRouter

# Definir d'une type GraphQL
@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "hello from GraphQL!"
    
    @strawberry.field
    def user(self) -> "User":
        return User(id=1, name="Alice", email="alice@example.com")
                    
schema = strawberry.Schema(query=Query)

# Créer une application FastAPI
app = FastAPI()

# Ajouter le routeur GraphQL
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
