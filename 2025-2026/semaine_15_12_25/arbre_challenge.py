clients = [
    { " id " : 1 , " age " : 25 , " ville " : " Paris " , " departement " : " 75 " } ,
    { " id " : 2 , " age " : 35 , " ville " : " Lyon " , " departement " : " 69 " } ,
    { " id " : 3 , " age " : 28 , " ville " : " Paris " , " departement " : " 75 " } ,
    { " id " : 4 , " age " : 42 , " ville " : " Marseille " , " departement " : " 13 " } ,
    { " id " : 5 , " age " : 31 , " ville " : " Lyon " , " departement " : " 69 " }
]

arbre = {"France": {}}

for client in clients:
    dep_key = f"{client[" departement "]} ({client[" ville "]})"

    if client["age"] < 30:
        groupe_age = "<30 ans"
    elif 30 <= client["age"] <= 40:
        groupe_age = "30-40 ans"
    else:
        groupe_age = ">40 ans"

    if dep_key not in arbre["France"]:
        arbre["France"][dep_key] = {}

    arbre["France"][dep_key][groupe_age].append(f"Client {client[' id ']}")

print("--- STRUCTURE ET COMPTAGE ---")
total_clients = 0

for pays, depts in arbre.items():
    print(pays)

    for dept_nom, ages in depts.items():

        nb_clients_dept = sum(len(c) for c in ages.values())
        print(f"  └── {dept_nom} : {nb_clients_dept} clients")

        for age_nom, liste_clients in ages.items():
            nb = len(liste_clients)
            total_clients += nb
            print(f"      └── {age_nom} : {nb}")
            print(f"          └── {', '.join(liste_clients)}")

print(f"\nTotal général France : {total_clients} clients")
            