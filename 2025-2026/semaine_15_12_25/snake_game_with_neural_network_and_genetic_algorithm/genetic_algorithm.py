import random
import numpy as np
from snake import Snake
from neural_network import NeuralNetwork

class GeneticAlgorithm:
    def __init__(self, size=50, mutation_rate=0.08, seed=42):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        self.size = size
        self.generation = 1
        self.mutation_rate = mutation_rate
        self.stagnation_counter = 0
        self.best_fitness_ever = 0
        self.history = []
        self.population = [Snake(NeuralNetwork(input_nodes=13)) for _ in range(size)]
    
    def evaluate(self):
        current_gen_best_fitness = 0
        max_score = 0
        all_fitnesses = []
        
        for snake in self.population:
            score, steps, approaches = self._run_simulation(snake)
            
            # FITNESS ÉQUILIBRÉE
            if score > 0:
                # Score au cube pour récompenser, mais pas écraser la diversité
                fitness = (score ** 3) * 1000 
                fitness += steps * 0.1 # Petit bonus de temps
            else:
                # Encourage à aller vers la nourriture même sans manger
                fitness = approaches * 2 + (steps * 0.05)
            
            snake.fitness = max(1, fitness)
            snake.score = score
            all_fitnesses.append(snake.fitness)
            
            if fitness > current_gen_best_fitness:
                current_gen_best_fitness = fitness
            if score > max_score:
                max_score = score
        
        self.history.append(np.mean(all_fitnesses))
        
        # Gestion de la stagnation
        if current_gen_best_fitness > self.best_fitness_ever:
            self.best_fitness_ever = current_gen_best_fitness
            self.stagnation_counter = 0
        else:
            self.stagnation_counter += 1
        
        print(f"Gen {self.generation} | Max Score: {max_score} | Best Fit: {int(current_gen_best_fitness)} | Stag: {self.stagnation_counter}")
        return True
    
    def select(self):
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        return self.population
    
    def reproduce(self, selected_pool):
        new_pop = []
        
        # 1. ÉLITISME (Garder les 3 meilleurs tels quels)
        for i in range(3):
            new_pop.append(Snake(NeuralNetwork(
                input_nodes=13, 
                weights=selected_pool[i].network.get_weights()
            )))
        
        # 2. GÉNÉRATION DES ENFANTS
        while len(new_pop) < self.size:
            # Sélection de 2 parents parmi les 15 meilleurs
            parents = random.sample(selected_pool[:15], 2)
            p1, p2 = parents[0], parents[1]
            
            # Crossover (Mélange des gènes)
            child_weights = []
            for w1, w2 in zip(p1.network.get_weights(), p2.network.get_weights()):
                # On crée un masque aléatoire pour choisir le gène de P1 ou P2
                mask = np.random.rand(*w1.shape) > 0.5
                child_weights.append(np.where(mask, w1, w2))
            
            child_net = NeuralNetwork(input_nodes=13, weights=child_weights)
            
            # Mutation adaptative (augmente si on stagne)
            m_rate = self.mutation_rate
            if self.stagnation_counter > 50:
                m_rate = 0.2  # Exploration forcée
                
            child_net.mutate(m_rate)
            new_pop.append(Snake(child_net))
        
        # --- SORTIR DE LA BOUCLE WHILE AVANT DE FINIR ---
        self.population = new_pop
        self.generation += 1
        return self.population
    
    def _run_simulation(self, snake):
        snake.reset()
        food = snake.generate_food()
        steps = 0
        max_steps = 600  # Budget de départ augmenté
        approaches = 0
        
        prev_dist = abs(snake.get_head()[0] - food[0]) + abs(snake.get_head()[1] - food[1])
        
        while snake.alive and steps < max_steps:
            snake.think(food)
            ate = snake.move(food)
            steps += 1
            
            if ate:
                food = snake.generate_food()
                # Budget MASSIF pour les longs snakes
                max_steps += (250 + snake.score * 50)
                snake.steps_without_food = 0
            else:
                curr_dist = abs(snake.get_head()[0] - food[0]) + abs(snake.get_head()[1] - food[1])
                if curr_dist < prev_dist:
                    approaches += 1
                prev_dist = curr_dist
        
        return snake.score, steps, approaches