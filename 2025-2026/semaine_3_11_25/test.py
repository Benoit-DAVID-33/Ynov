class Node:
    def __init__(self):
        self.data = ""
        self.next = None

# Création des nœuds
head = Node()
head.next = Node()
head.next.next = Node()

# Affichage
current = head
while current is not None:
    print(f"[{current.data}]")
    current = current.next