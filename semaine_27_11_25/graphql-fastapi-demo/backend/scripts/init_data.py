import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database import engine, SessionLocal
from app.database.models import User

def init_database():
    # Créer les tables
    User.metadata.create_all(bind=engine)

    db = SessionLocal()

    # Vérifier si des données existent déjà
    if db.query(User).count() == 0:
        users = [
            User(name="Alice Dupont", email="alice@example.com"),
            User(name="Bob Martin", email="bob@example.com"),
            User(name="Charlie Durand", email="charlie@example.com")
        ]
        db.add_all(users)
        db.commit()
        print("Données initiales créees avec succès.")
    else:
        print("La base contient déjà des données.")

    db.close()

if __name__ == "__main__":
    init_database()