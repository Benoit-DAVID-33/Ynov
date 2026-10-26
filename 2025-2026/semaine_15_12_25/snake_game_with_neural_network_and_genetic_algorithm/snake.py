import random
import numpy as np
from neural_network import NeuralNetwork
try:
    from config import GRID_WIDTH, GRID_HEIGHT
except ImportError:
    GRID_WIDTH, GRID_HEIGHT = 20, 20

DIRECTIONS = [(0,-1), (1,0), (0,1), (-1,0)]

class Snake:
    def __init__(self, network=None):
        
        self.network = network if network else NeuralNetwork()
        self.direction_changes = 0 
        self.reset()

    def reset(self):
        # On place la tête
        head_x, head_y = GRID_WIDTH // 2, GRID_HEIGHT // 2
        self.direction = random.choice(DIRECTIONS)
        
        # ON INITIALISE LE CORPS (3 segments au lieu d'un seul)
        self.positions = []
        for i in range(3):
            # On place les segments derrière la tête selon la direction
            self.positions.append((head_x - self.direction[0] * i, 
                                head_y - self.direction[1] * i))
        
        self.length = 3
        self.alive = True
        self.score = 0
        self.steps = 0
        self.steps_without_food = 0
        self.fitness = 0
        self.direction_changes = 0

    # --- AJOUT CRITIQUE POUR L'ALGO GÉNÉTIQUE ---
    def play(self):
        self.reset()
        food = self.generate_food()
        
        while self.alive:
            
            self.think(food)
            ate_food = self.move(food)
            if ate_food:
                food = self.generate_food()
                
            if self.steps > 2000: 
                self.alive = False

    def generate_food(self):
        while True:
            x = random.randint(0, GRID_WIDTH - 1)
            y = random.randint(0, GRID_HEIGHT - 1)
            if (x, y) not in self.positions:
                return (x, y)
    # ---------------------------------------------

    def get_head(self):
        return self.positions[0]

    def turn(self, d):
        # Empêche le demi-tour immédiat (ex: aller bas quand on va haut)
        if (d[0] * -1, d[1] * -1) != self.direction:
            
            # Si la nouvelle direction est différente de l'actuelle, on compte un virage
            if self.direction != d:
                self.direction_changes += 1
                
            self.direction = d

    def move(self, food):
        if not self.alive:
            return False

        x, y = self.get_head()
        nx = x + self.direction[0]
        ny = y + self.direction[1]

        # MORT SI SORTIE DE GRILLE (Plus simple pour l'IA au début)
        if nx < 0 or nx >= GRID_WIDTH or ny < 0 or ny >= GRID_HEIGHT:
            self.alive = False
            return False

        new = (nx, ny)

        # MORT SI COLLISION CORPS
        if new in self.positions[:-1]:
            self.alive = False
            return False

        self.positions.insert(0, new)

        if new == food:
            self.score += 1
            self.length += 1
            self.steps_without_food = 0 # Reset crucial
            return True

        self.positions.pop()
        self.steps += 1
        self.steps_without_food += 1

        # Limite de survie plus généreuse
        if self.steps_without_food > 150: 
            self.alive = False

        return False

    def get_vision(self, food):
        hx, hy = self.get_head()
        
        # 1. Direction relative nourriture (Normalisée entre -1 et 1)
        dist_food_x = (food[0] - hx) / GRID_WIDTH
        dist_food_y = (food[1] - hy) / GRID_HEIGHT
        
        # 2. Vision des obstacles (Raycasting 4 directions sans modulo)
        # On regarde : Mur ou Corps ?
        surroundings = []
        for dx, dy in DIRECTIONS:
            obs_dist = 0
            for i in range(1, max(GRID_WIDTH, GRID_HEIGHT)):
                tx, ty = hx + dx * i, hy + dy * i
                # Si on touche un mur ou le corps
                if not (0 <= tx < GRID_WIDTH and 0 <= ty < GRID_HEIGHT) or (tx, ty) in self.positions:
                    obs_dist = 1.0 / i  # Plus c'est proche, plus la valeur est haute
                    break
            surroundings.append(obs_dist)
        
        # 3. Direction actuelle (One-hot encoding)
        current_dir = [1 if self.direction == d else 0 for d in DIRECTIONS]
        
        # 4. Longueur (Normalisée)
        norm_length = [self.length / (GRID_WIDTH * GRID_HEIGHT)]

        # Total : 2 (food) + 4 (obs) + 4 (dir) + 1 (len) = 11 inputs
        # Ton réseau attend 13 ? On ajoute 2 neutres pour ne pas crash ton NN actuel
        vision = [dist_food_x, dist_food_y] + surroundings + current_dir + norm_length + [0, 0]
        
        return np.array(vision)
    
    
    def think(self, food):
        
        state = self.get_vision(food)
        if hasattr(self.network, 'predict'):
            out = self.network.predict(state)
        else:
            out = self.network.forward(state)

        # Si ton output layer a 4 neurones (Haut, Droite, Bas, Gauche):
        self.turn(DIRECTIONS[np.argmax(out)])

    def calculate_fitness(self):
        self.fitness = (
            self.score * 1000
            + self.steps * 0.1
            - self.steps_without_food * 0.5
        )
        
        if self.score == 0:
            self.fitness = max(1, self.steps * 0.1)
            
        return max(0, self.fitness)
    
    