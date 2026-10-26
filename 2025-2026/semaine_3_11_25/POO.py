class Personne:
    def __init__(self, nom, age):
        self.nom = nom
        self.age = age

    def presentation(self):
        print(f"Je m’appelle {self.nom} et j’ai {self.age} ans.")

# Création d'une instance
p1 = Personne("Alice", 30)


p1.presentation()



class Personne:
    def __init__(self, nom:str, age:int):
        self.nom = nom
        self.age = age

    def presentation(self):
        print(f"Je m'appelle {self.nom} et j'ai {self.age} ans.")

p1 = Personne("Bernard", 67)

p1.presentation()


class CompteBancaire:
    def __init__(self, titulaire: str, solde: float = 0.0):
        self.titulaire = titulaire
        self.solde = solde

    def deposer(self, montant: float):
        if montant > 0:
            self.solde += montant
        else:
            print("Le montant à déposer doit être positif.")

    def retirer(self, montant: float):
        if montant > 0:
            if montant <= self.solde:
                self.solde -= montant
            else:
                print("Fonds insuffisants.")
        else:
            print("Le montant à retirer doit être positif.")

    def afficher_solde(self):
        print(f"Solde de {self.titulaire} : {self.solde:.2f} €")

# Création d'un compte
compte1 = CompteBancaire("Bernard", 100.0)

compte1.deposer(50)

compte1.retirer(30)

compte1.afficher_solde()




class Personne:
    def __init__(self, nom: str, age: int):
        self.nom = nom
        self.age = age

    def presentation(self):
        print(f"Je m’appelle {self.nom} et j’ai {self.age} ans.")


class Etudiant(Personne):
    def __init__(self, nom: str, age: int, niveau: str):
        super().__init__(nom, age)
        self.niveau = niveau

    def etudier(self):
        print(f"{self.nom} étudie au niveau {self.niveau}.")


# Création d'une instance d'étudiant
e1 = Etudiant("Benoît", 24, "Master IA")

e1.presentation()
e1.etudier()




class Animal:
    def parler(self):
        print("Cet animal fait un bruit.")

class Chien(Animal):
    def parler(self):
        print("Le chien aboie : Ouaf !")

class Chat(Animal):
    def parler(self):
        print("Le chat miaule : Miaou !")

# Création des instances
animaux = [Chien(), Chat(), Animal()]

for animal in animaux:
    animal.parler()





class Voiture:
    def __init__(self, marque: str, vitesse: int = 0):
        self.__marque = marque
        self.__vitesse = vitesse 

    # Méthodes publiques pour lire les attributs
    def get_marque(self):
        return self.__marque

    def get_vitesse(self):
        return self.__vitesse

    # Méthodes publiques pour modifier les attributs
    def set_marque(self, nouvelle_marque: str):
        self.__marque = nouvelle_marque

    def set_vitesse(self, nouvelle_vitesse: int):
        if nouvelle_vitesse >= 0:
            self.__vitesse = nouvelle_vitesse
        else:
            print("La vitesse ne peut pas être négative.")


# Création d'une voiture
v1 = Voiture("Renault", 50)

print(v1.get_marque())
print(v1.get_vitesse())

v1.set_vitesse(80)
v1.set_marque("Peugeot")

print(v1.get_marque())
print(v1.get_vitesse())