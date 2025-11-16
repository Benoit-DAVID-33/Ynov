from pydantic import BaseModel
from fastapi import HTTPException

class Utilisateur(BaseModel):
    nom: str
    age: int
    email: str

@app.post("/utilisateur/")
def creer_utilisateur(user: Utilisateur):
    return {"message": f"Utilisateur {user.nom} ajouté avec succès."}

users_db = []

def create_user(user_data):
    for u in users_db:
        if u["email"] == user_data.email:
            raise HTTPException(status_code=400, detail="Email already registered")
 
    new_user = {
        "id": len(users_db) + 1,
        "name": user_data.name,
        "email": user_data.email
    }
    user_data.append(new_user)
    return new_user