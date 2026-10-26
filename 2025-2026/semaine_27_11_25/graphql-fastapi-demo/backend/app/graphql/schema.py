import strawberry
from typing import List, Optional
# Assure-toi que ces imports pointent vers les bons fichiers dans ton projet
from app.services.user_service import UserService
from app.database.database import get_db

@strawberry.type
class User:
    id: int
    name: str
    email: str

@strawberry.input
class UserInput:
    name: str
    email: str

@strawberry.input
class UserFilter:
    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None

@strawberry.type
class Query:
    @strawberry.field
    def users(
        self,
        filter: Optional[UserFilter] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        # Récupération de la session DB
        db = next(get_db())

        filter_dict = {}
        if filter:
            filter_dict = {
                'user_id': filter.id,
                'name': filter.name,
                'email': filter.email
            }

        # Appel au service en filtrant les valeurs None
        users = UserService.get_users(
            db=db,
            skip=skip,
            limit=limit,
            **{k: v for k, v in filter_dict.items() if v is not None}
        )

        # Conversion des modèles SQLAlchemy en type Strawberry User
        return [
            User(id=user.id, name=user.name, email=user.email)
            for user in users
        ]

    @strawberry.field
    def user(self, id: int) -> Optional[User]:
        db = next(get_db())
        user = UserService.get_user_by_id(db, id)
        if user:
            return User(id=user.id, name=user.name, email=user.email)
        return None

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, user_input: UserInput) -> User:
        db = next(get_db())
        try:
            new_user = UserService.create_user(
                db=db,
                name=user_input.name,
                email=user_input.email
            )
            return User(
                id=new_user.id,
                name=new_user.name,
                email=new_user.email
            )
        except ValueError as e:
            raise Exception(str(e))

    @strawberry.mutation
    def update_user(self, id: int, user_input: UserInput) -> Optional[User]:
        db = next(get_db())
        user = UserService.update_user(
            db, 
            id, 
            user_input.name, 
            user_input.email
        )
        if user:
            return User(id=user.id, name=user.name, email=user.email)
        return None

    @strawberry.mutation
    def delete_user(self, id: int) -> bool:
        db = next(get_db())
        return UserService.delete_user(db, id)

schema = strawberry.Schema(query=Query, mutation=Mutation)