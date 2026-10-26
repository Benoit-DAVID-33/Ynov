from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from .graphql.schema import schema

def create_application() -> FastAPI:
    app = FastAPI(
        title="GraphQL FastAPI Demo",
        description="API Graphq avec FastAPI et SQLite.",
        version="1.0.0",
    )

    # Confirgurer CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Router GraphQL
    graphql_app = GraphQLRouter(schema)
    app.include_router(graphql_app, prefix="/graphql")

    # Routes sant
    @app.get("/")
    async def read_root():
        return {"message": "GraphQL API is runnig"}
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    return app

app = create_application()