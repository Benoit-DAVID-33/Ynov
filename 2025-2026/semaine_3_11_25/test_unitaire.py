class CompteBancaire:
    def __init__(self, titulaire: str, solde: float = 0.0):
        self.titulaire = titulaire
        self.solde = solde

    def deposer(self, montant: float):
        if montant > 0:
            self.solde += montant

    def retirer(self, montant: float):
        if 0 < montant <= self.solde:
            self.solde -= montant

    def get_solde(self):
        return self.solde
    

def fibonacci(n: int) -> int:
    if n < 0:
        raise ValueError("n doit être positif")
    if n in [0, 1]:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def fibonacci(n: int) -> int:
    if n < 0:
        raise ValueError("n doit être positif")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


class TodoList:
    def __init__(self):
        self.taches = {}

    def ajouter(self, nom: str):
        self.taches[nom] = False

    def terminer(self, nom: str):
        if nom in self.taches:
            self.taches[nom] = True

    def supprimer(self, nom: str):
        if nom in self.taches:
            del self.taches[nom]



def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("n doit être positif")
    return 1 if n == 0 else n * factorial(n - 1)

def isprime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0:
            return False
    return True

def gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a



import csv

def lire_csv(path: str) -> dict:
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]
    



class Logger:
    def __init__(self, fichier: str):
        self.logs = []
        self.fichier = fichier

    def log(self, message: str):
        self.logs.append(message)

    def save(self):
        with open(self.fichier, 'a', encoding='utf-8') as f:
            for log in self.logs:
                f.write(log + '\n')


class Livre:
    def __init__(self, titre: str, auteur: str):
        self.titre = titre
        self.auteur = auteur

class Bibliotheque:
    def __init__(self):
        self.livres = []

    def ajouter(self, livre: Livre):
        self.livres.append(livre)

    def retirer(self, titre: str):
        self.livres = [l for l in self.livres if l.titre != titre]

    def rechercher(self, mot_cle: str):
        return [l for l in self.livres if mot_cle.lower() in l.titre.lower()]
    


compte = CompteBancaire("Alice", 100)
compte.deposer(50)
compte.retirer(30)
print(f"Solde de {compte.titulaire} : {compte.get_solde()} €")  # Solde de Alice : 120.0 €


print("Fibonacci(0):", fibonacci(0))  # 0
print("Fibonacci(1):", fibonacci(1))  # 1
print("Fibonacci(10):", fibonacci(10))  # 55

todo = TodoList()
todo.ajouter("Réviser POO")
todo.ajouter("Faire TP TDD")
todo.terminer("Réviser POO")
todo.supprimer("Faire TP TDD")
print("Tâches restantes :", todo.taches)  # {'Réviser POO': True}

print("Factorial(5):", factorial(5))  # 120
print("Isprime(7):", isprime(7))      # True
print("Isprime(8):", isprime(8))      # False
print("GCD(48, 18):", gcd(48, 18))    # 6

logger = Logger("logs.txt")
logger.log("Démarrage du programme")
logger.log("Opération réussie")
logger.save()
print("Logs en mémoire :", logger.logs)

livre1 = Livre("Python pour les nuls", "Jean Dupont")
livre2 = Livre("Master IA", "Benoît")

biblio = Bibliotheque()
biblio.ajouter(livre1)
biblio.ajouter(livre2)
biblio.retirer("Python pour les nuls")

resultats = biblio.rechercher("IA")
for livre in resultats:
    print(f"Livre trouvé : {livre.titre} par {livre.auteur}")
# Livre trouvé : Master IA par Benoît





