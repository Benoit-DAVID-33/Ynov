from functools import reduce
def composer(*fonctions):
    return reduce(lambda f, g: lambda x: f(g(x)), fonctions)

def ajouter_1(x): return x + 1
def multiplier_2(x): return x * 2
def carre(x): return x ** 2

transformation = composer(carre, multiplier_2, ajouter_1)
resultat = transformation(7)

print(f"transformation du 7 {resultat}")

def pipe(*fonctions):
    return reduce(lambda f, g: lambda x: g(f(x)), fonctions)

transformation_pipe = pipe(ajouter_1, multiplier_2, carre)
resultat_pipe = transformation_pipe(3)
print(f"transormation pipe de 3 {resultat_pipe}")