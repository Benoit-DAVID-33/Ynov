import pygame
import random
import math
from enum import Enum

# Constantes nécessaires pour les classes
SCREEN_WIDTH = 1500
SCREEN_HEIGHT = 800
BULLET_COLOR = (255, 220, 80)

class EntityType(Enum):
    HUMAN = 1
    ZOMBIE = 2

class Human:
    def __init__(self, x, y, chromosome=None, generation=1):
        self.x = x
        self.y = y
        self.radius = 10
        self.health = 100
        self.ammo = 20
        self.reload_time = 0
        self.speed = 2.0
        self.vision = 100
        self.accuracy = 0.7
        self.ammo_capacity = 30
        self.alive = True
        self.fitness = 0
        self.kills = 0
        self.damage_dealt = 0
        self.time_alive = 0
        self.generation = generation
        self.id = random.randint(1000, 9999)
        
        # Chromosome: [vitesse, vision, précision, capacité munitions, agressivité]
        if chromosome:
            self.chromosome = chromosome
        else:
            self.chromosome = [
                random.uniform(2.5, 4.0),    # <--- MODIFIÉ : Vitesse min/max augmentée
                random.uniform(60, 180),     # vision
                random.uniform(0.4, 0.9),    # précision
                random.uniform(20, 40),      # capacité munitions
                random.uniform(0.2, 0.8)     # agressivité
            ]
        self.apply_chromosome()
    
    def apply_chromosome(self):
        self.speed = self.chromosome[0]
        self.vision = self.chromosome[1]
        self.accuracy = self.chromosome[2]
        self.ammo_capacity = int(self.chromosome[3])
        self.aggressiveness = self.chromosome[4]
    
    def move(self, dx, dy, walls):
        new_x = self.x + dx * self.speed
        new_y = self.y + dy * self.speed
        
        # Collision avec les murs
        for wall in walls:
            if self.collides_with_wall(new_x, new_y, wall):
                if not self.collides_with_wall(self.x + dx * self.speed, self.y, wall):
                    new_y = self.y
                elif not self.collides_with_wall(self.x, self.y + dy * self.speed, wall):
                    new_x = self.x
                else:
                    return
        
        self.x = max(self.radius, min(SCREEN_WIDTH - self.radius, new_x))
        self.y = max(self.radius, min(SCREEN_HEIGHT - self.radius, new_y))
    
    def collides_with_wall(self, x, y, wall):
        return (x + self.radius > wall[0] and x - self.radius < wall[0] + wall[2] and
                y + self.radius > wall[1] and y - self.radius < wall[1] + wall[3])
    
    def update(self, zombies, ammo_packs, walls):
        if not self.alive: return
        self.time_alive += 1
        if self.reload_time > 0: self.reload_time -= 1
        
        # Vision
        zombies_in_range = []
        for zombie in zombies:
            if zombie.alive:
                dist = math.sqrt((self.x - zombie.x)**2 + (self.y - zombie.y)**2)
                if dist < self.vision:
                    zombies_in_range.append((zombie, dist))
        
        # Munitions
        nearest_ammo = None
        min_ammo_dist = float('inf')
        for ammo in ammo_packs:
            dist = math.sqrt((self.x - ammo.x)**2 + (self.y - ammo.y)**2)
            if dist < self.vision and dist < min_ammo_dist:
                min_ammo_dist = dist
                nearest_ammo = ammo

        # Décision IA
        if zombies_in_range:
            zombies_in_range.sort(key=lambda x: x[1])
            nearest_zombie, distance = zombies_in_range[0]
            
            dx = nearest_zombie.x - self.x
            dy = nearest_zombie.y - self.y
            dist_vec = max(0.1, math.sqrt(dx**2 + dy**2)) # Pour normaliser

            # Fuite ou Combat
            if distance < 40: # Trop près !
                self.move(-(dx/dist_vec), -(dy/dist_vec), walls) # Fuir à l'opposé
                if self.aggressiveness > 0.6 and self.ammo > 0 and self.reload_time == 0:
                    return self.shoot(nearest_zombie)
            
            elif distance < 100:
                if self.aggressiveness > 0.5: # Attaquer
                    if distance > 80: self.move(dx/dist_vec * 0.7, dy/dist_vec * 0.7, walls)
                    else: self.move(-(dx/dist_vec) * 0.3, -(dy/dist_vec) * 0.3, walls)
                    
                    if self.reload_time == 0 and random.random() < (self.accuracy * self.aggressiveness):
                        return self.shoot(nearest_zombie)
                else: # Fuir prudemment
                    self.move(-(dx/dist_vec) * 0.5, -(dy/dist_vec) * 0.5, walls)
            
            else: # Loin
                if self.aggressiveness > 0.7: # Se rapprocher
                    self.move(dx/dist_vec * 0.4, dy/dist_vec * 0.4, walls)

        elif nearest_ammo and self.ammo < self.ammo_capacity * 0.4:
            dx = nearest_ammo.x - self.x
            dy = nearest_ammo.y - self.y
            dist = max(0.1, math.sqrt(dx**2 + dy**2))
            self.move(dx/dist, dy/dist, walls)
            
        else:
            # --- MODIFICATION ICI : EXPLORATION CONTINUE ---
            # Au lieu de bouger 10% du temps, on bouge tout le temps
            
            # Vitesse d'exploration selon le tempérament
            if self.aggressiveness > 0.6:
                wander_speed = 0.8  # Rapide
            else:
                wander_speed = 0.4  # Prudent
            
            # Direction aléatoire
            dx = random.uniform(-1, 1)
            dy = random.uniform(-1, 1)
            dist = max(0.1, math.sqrt(dx**2 + dy**2))
            
            self.move((dx/dist) * wander_speed, (dy/dist) * wander_speed, walls)

        # Ramassage munitions
        for ammo in ammo_packs[:]:
            dist = math.sqrt((self.x - ammo.x)**2 + (self.y - ammo.y)**2)
            if dist < self.radius + ammo.radius:
                self.ammo = min(self.ammo_capacity, self.ammo + ammo.amount)
                ammo_packs.remove(ammo)
                break
        return None

    def shoot(self, target):
        if self.ammo <= 0 or self.reload_time > 0: return None
        self.ammo -= 1
        self.reload_time = max(8, 15 - int(self.aggressiveness * 10))
        base_damage = 20 + (self.aggressiveness * 10)
        if random.random() > self.accuracy: base_damage *= 0.6
        self.damage_dealt += base_damage
        return Bullet(self.x, self.y, target.x, target.y, base_damage, self.accuracy)

    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0: self.alive = False
        return not self.alive

    def draw(self, screen, show_vision=False):
        if not self.alive: return
        color_intensity = min(255, 100 + int(self.aggressiveness * 155))
        pygame.draw.circle(screen, (70, color_intensity, 255), (int(self.x), int(self.y)), self.radius)
        
        # Barre de vie
        pygame.draw.rect(screen, (255, 40, 40), (self.x-10, self.y-18, 20, 3))
        pygame.draw.rect(screen, (50, 255, 50), (self.x-10, self.y-18, 20 * (self.health/100), 3))
        
        if show_vision:
            surf = pygame.Surface((self.vision*2, self.vision*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (100, 100, 255, 30), (self.vision, self.vision), self.vision)
            screen.blit(surf, (self.x - self.vision, self.y - self.vision))

class Zombie:
    def __init__(self, x, y, difficulty=1):
        self.x = x
        self.y = y
        self.radius = 12
        self.base_health = 80
        self.base_speed = 1.0
        self.difficulty = difficulty
        self.health = self.base_health * (1 + (difficulty-1) * 0.3)
        self.speed = self.base_speed * (1 + (difficulty-1) * 0.2)
        self.damage = 5 + (difficulty-1) * 2
        self.attack_cooldown = 0
        self.alive = True
        self.type = random.choice(['normal', 'rusher', 'tank'])[:difficulty]
        
        if self.type == 'rusher':
            self.speed *= 1.5; self.health *= 0.8
        elif self.type == 'tank':
            self.speed *= 0.8; self.health *= 1.5; self.damage *= 1.2

    def collides_with_wall(self, x, y, wall):
        return (x + self.radius > wall[0] and x - self.radius < wall[0] + wall[2] and
                y + self.radius > wall[1] and y - self.radius < wall[1] + wall[3])

    def move_towards_target(self, target_x, target_y, walls):
        dx = target_x - self.x
        dy = target_y - self.y
        dist = max(0.1, math.sqrt(dx**2 + dy**2))
        move_x = (dx / dist) * self.speed
        move_y = (dy / dist) * self.speed
        
        new_x, new_y = self.x + move_x, self.y + move_y
        
        collision = False
        for wall in walls:
            if self.collides_with_wall(new_x, new_y, wall):
                collision = True
                # Glissement le long des murs
                if not self.collides_with_wall(self.x + move_x, self.y, wall):
                    new_y = self.y
                    collision = False
                elif not self.collides_with_wall(self.x, self.y + move_y, wall):
                    new_x = self.x
                    collision = False
                else:
                    return False
                break
        
        self.x = max(self.radius, min(SCREEN_WIDTH - self.radius, new_x))
        self.y = max(self.radius, min(SCREEN_HEIGHT - self.radius, new_y))
        return not collision

    def update(self, humans, walls):
        if not self.alive: return None
        nearest_human = None
        min_dist = float('inf')
        for human in humans:
            if human.alive:
                dist = math.sqrt((self.x - human.x)**2 + (self.y - human.y)**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_human = human
        
        if nearest_human:
            self.move_towards_target(nearest_human.x, nearest_human.y, walls)
            if min_dist < self.radius + nearest_human.radius + 8 and self.attack_cooldown <= 0:
                self.attack_cooldown = 25 - (self.difficulty * 3)
                return nearest_human
        else:
            if random.random() < 0.1:
                self.move_towards_target(self.x + random.uniform(-50,50), self.y + random.uniform(-50,50), walls)
        
        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        return None

    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.alive = False
            return True
        return False

    def draw(self, screen):
        if not self.alive: return
        color = (80, 240, 80) if self.type == 'rusher' else (40, 180, 40) if self.type == 'tank' else (60, 220, 60)
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        # Yeux
        eye_color = (200 + self.difficulty * 10, 50, 50)
        pygame.draw.circle(screen, eye_color, (int(self.x - 3), int(self.y - 3)), 3)
        pygame.draw.circle(screen, eye_color, (int(self.x + 3), int(self.y - 3)), 3)

class Bullet:
    def __init__(self, x, y, target_x, target_y, damage, accuracy):
        self.x = x; self.y = y; self.radius = 3
        self.speed = 8 + (accuracy * 4)
        self.damage = damage; self.alive = True
        
        dx = target_x - x + random.uniform(-10 * (1-accuracy), 10 * (1-accuracy))
        dy = target_y - y + random.uniform(-10 * (1-accuracy), 10 * (1-accuracy))
        dist = max(0.1, math.sqrt(dx**2 + dy**2))
        self.vx = (dx/dist) * self.speed
        self.vy = (dy/dist) * self.speed

    def update(self, walls):
        self.x += self.vx; self.y += self.vy
        for wall in walls:
            if (self.x > wall[0] and self.x < wall[0] + wall[2] and
                self.y > wall[1] and self.y < wall[1] + wall[3]):
                self.alive = False; return
        if (self.x < -50 or self.x > SCREEN_WIDTH + 50 or self.y < -50 or self.y > SCREEN_HEIGHT + 50):
            self.alive = False

    def draw(self, screen):
        pygame.draw.circle(screen, BULLET_COLOR, (int(self.x), int(self.y)), self.radius)

class AmmoPack:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 8
        self.amount = random.randint(8, 20)
        self.blink_timer = random.randint(0, 60)

    def update(self):
        self.blink_timer = (self.blink_timer + 1) % 120

    def draw(self, screen):
        alpha = 128 + int(math.sin(self.blink_timer * 0.1) * 100)
        
        surf = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 80, 80, alpha), (self.radius, self.radius), self.radius)
        screen.blit(surf, (int(self.x - self.radius), int(self.y - self.radius)))
        
        blink_factor = 0.5 + math.sin(self.blink_timer * 0.2) * 0.5
        plus_width = max(1, int(2 * blink_factor))
        plus_size = 4
        
        # Ligne horizontale
        pygame.draw.line(screen, (255, 255, 255), 
                         (int(self.x - plus_size), int(self.y)), 
                         (int(self.x + plus_size), int(self.y)), plus_width)
        # Ligne verticale
        pygame.draw.line(screen, (255, 255, 255), 
                         (int(self.x), int(self.y - plus_size)), 
                         (int(self.x), int(self.y + plus_size)), plus_width)

# --- ALGORITHME GÉNÉTIQUE COMPLET ---
class GeneticAlgorithm:
    def __init__(self, population_size=20):
        self.population_size = population_size
        self.mutation_rate = 0.25
        self.mutation_strength = 0.4
        self.elitism_count = 2
        self.generation_stats = []

    def calculate_fitness(self, human):
        if not human.alive and human.time_alive == 0:
            human.fitness = 0
            return 0
        w_time = 1.0
        w_damage = 0.5
        w_kill = 50.0
        score = (human.time_alive * w_time) + (human.damage_dealt * w_damage) + (human.kills * w_kill)
        human.fitness = score
        return score

    def selection(self, humans):
        for h in humans: self.calculate_fitness(h)
        humans_sorted = sorted(humans, key=lambda h: h.fitness, reverse=True)
        # Stats rapide
        if humans_sorted:
            print(f"Meilleur Fitness: {int(humans_sorted[0].fitness)}")
        selection_count = max(2, len(humans_sorted) // 2)
        return humans_sorted[:selection_count]

    def crossover(self, parent1_chromo, parent2_chromo):
        size = len(parent1_chromo)
        if size < 2: return parent1_chromo.copy()
        point1 = random.randint(0, size - 2)
        point2 = random.randint(point1 + 1, size - 1)
        return parent1_chromo[:point1] + parent2_chromo[point1:point2] + parent1_chromo[point2:]

    def mutate(self, chromosome, generation):
        current_rate = self.mutation_rate * (1.0 - min(generation / 50.0, 0.5))
        mutated = chromosome.copy()
        for i in range(len(mutated)):
            if random.random() < current_rate:
                mutated[i] += random.gauss(0, self.mutation_strength)
        # Clamping
        mutated[0] = max(0.5, min(4.0, mutated[0])) # Vitesse
        mutated[1] = max(50, min(300, mutated[1]))  # Vision
        mutated[2] = max(0.1, min(1.0, mutated[2])) # Précision
        mutated[3] = max(10, min(100, mutated[3]))  # Munitions
        mutated[4] = max(0.0, min(1.0, mutated[4])) # Agressivité
        return mutated

    def create_new_generation(self, humans, generation):
        new_chromosomes = []
        parents = self.selection(humans)
        if not parents: return [h.chromosome.copy() for h in humans]

        # Elitisme
        for i in range(min(self.elitism_count, len(parents))):
            new_chromosomes.append(parents[i].chromosome.copy())
            
        # Reproduction
        while len(new_chromosomes) < self.population_size:
            p1 = random.choice(parents)
            p2 = random.choice(parents)
            child = self.crossover(p1.chromosome, p2.chromosome)
            child = self.mutate(child, generation)
            new_chromosomes.append(child)
            
        return new_chromosomes