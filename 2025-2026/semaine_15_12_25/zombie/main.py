import pygame
import random
import math
import numpy as np
# ON IMPORTE TOUT DEPUIS CLASSES.PY
from classes import Human, Zombie, Bullet, AmmoPack, GeneticAlgorithm, SCREEN_WIDTH, SCREEN_HEIGHT

# Initialisation de Pygame
pygame.init()

# Constantes du jeu
FPS = 60

# Couleurs
BACKGROUND = (15, 15, 35)
TEXT_COLOR = (230, 230, 230)
UI_BG = (25, 25, 55, 220)
GRID_COLOR = (100, 100, 150, 50)

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Évolution des Survivants - Algorithme Génétique")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', 22)
        self.big_font = pygame.font.SysFont('Arial', 40)
        self.small_font = pygame.font.SysFont('Arial', 18)
        
        # Zone de jeu limitée
        self.play_area = pygame.Rect(60, 60, SCREEN_WIDTH - 120, SCREEN_HEIGHT - 120)
        
        # Groupes d'entités
        self.humans = []
        self.zombies = []
        self.bullets = []
        self.ammo_packs = []
        self.walls = []
        
        # Algorithm génétique
        self.ga = GeneticAlgorithm(population_size=20)
        self.generation = 1
        self.total_kills = 0
        self.best_fitness_history = []
        self.average_fitness_history = []
        
        # Statistiques
        self.game_time = 0
        self.max_humans = 20
        self.max_zombies = 50
        self.zombie_spawn_timer = 0
        self.ammo_spawn_timer = 0
        self.difficulty_level = 1
        self.zombies_killed_this_gen = 0
        self.wave_number = 2 
        self.zombies_to_spawn = 0
        self.wave_in_progress = False
        self.wave_cooldown = 0
        
        # État du jeu
        self.paused = False
        self.show_stats = True
        self.show_vision = False
        self.auto_next_gen = False
        self.manual_generation_control = True
        
        # Options de difficulté
        self.difficulty_settings = {
            'easy': {'max_zombies': 30, 'spawn_rate': 120, 'wave_size': 10},
            'normal': {'max_zombies': 50, 'spawn_rate': 90, 'wave_size': 15},
            'hard': {'max_zombies': 80, 'spawn_rate': 60, 'wave_size': 20},
            'insane': {'max_zombies': 500, 'spawn_rate': 30, 'wave_size': 30}
        }
        self.current_difficulty = 'normal'
        
        # Interface
        self.next_gen_button = pygame.Rect(SCREEN_WIDTH - 220, SCREEN_HEIGHT - 60, 200, 40)
        self.pause_button = pygame.Rect(SCREEN_WIDTH - 220, SCREEN_HEIGHT - 110, 200, 40)
        self.difficulty_buttons = {
            'easy': pygame.Rect(20, SCREEN_HEIGHT - 100, 100, 30),
            'normal': pygame.Rect(130, SCREEN_HEIGHT - 100, 100, 30),
            'hard': pygame.Rect(240, SCREEN_HEIGHT - 100, 100, 30),
            'insane': pygame.Rect(350, SCREEN_HEIGHT - 100, 100, 30)
        }
        
        self.apply_difficulty_settings()
        self.create_walls()
        self.initialize_population()
        self.start_wave()
    
    def apply_difficulty_settings(self):
        settings = self.difficulty_settings[self.current_difficulty]
        self.max_zombies = settings['max_zombies']
        self.zombie_spawn_rate = settings['spawn_rate']
        self.base_wave_size = settings['wave_size']
        self.difficulty_level = {'easy': 1.0, 'normal': 1.5, 'hard': 2.0, 'insane': 3.0}[self.current_difficulty]
    
    def create_walls(self):
        self.walls = [
            (40, 40, SCREEN_WIDTH - 80, 20), (40, SCREEN_HEIGHT - 60, SCREEN_WIDTH - 80, 20),
            (40, 40, 20, SCREEN_HEIGHT - 80), (SCREEN_WIDTH - 60, 40, 20, SCREEN_HEIGHT - 80),
            (200, 100, 15, 300), (400, 150, 200, 15), (650, 100, 15, 250),
            (300, 300, 200, 15), (500, 350, 15, 150), (750, 250, 150, 15),
            (200, 450, 300, 15), (600, 450, 200, 15), (400, 500, 15, 150),
            (800, 500, 15, 150), (150, 200, 80, 80), (900, 150, 100, 100),
            (350, 600, 120, 80), (800, 350, 100, 80), (550, 600, 150, 15),
            (300, 100, 15, 80), (900, 400, 15, 150),
        ]
    
    def initialize_population(self):
        spawn_points = self.get_valid_spawn_points(self.ga.population_size)
        for i in range(self.ga.population_size):
            if i < len(spawn_points): x, y = spawn_points[i]
            else: x, y = random.randint(100, SCREEN_WIDTH - 100), random.randint(100, SCREEN_HEIGHT - 100)
            human = Human(x, y, generation=self.generation)
            human.ammo_used = 0
            self.humans.append(human)
    
    def get_valid_spawn_points(self, count):
        points = []
        attempts = 0
        while len(points) < count and attempts < 1000:
            x = random.randint(self.play_area.left, self.play_area.right)
            y = random.randint(self.play_area.top, self.play_area.bottom)
            valid = True
            for wall in self.walls:
                if (x + 25 > wall[0] and x - 25 < wall[0] + wall[2] and y + 25 > wall[1] and y - 25 < wall[1] + wall[3]):
                    valid = False; break
            if valid:
                too_close = False
                for px, py in points:
                    if math.sqrt((x - px)**2 + (y - py)**2) < 60: too_close = True; break
                if not too_close: points.append((x, y))
            attempts += 1
        return points
    
    def get_valid_zombie_spawn_point(self):
        attempts = 0
        while attempts < 100:
            side = random.randint(0, 3)
            if side == 0: x, y = random.randint(self.play_area.left, self.play_area.right), self.play_area.top - 30
            elif side == 1: x, y = self.play_area.right + 30, random.randint(self.play_area.top, self.play_area.bottom)
            elif side == 2: x, y = random.randint(self.play_area.left, self.play_area.right), self.play_area.bottom + 30
            else: x, y = self.play_area.left - 30, random.randint(self.play_area.top, self.play_area.bottom)
            
            valid = True
            for wall in self.walls:
                if (x + 15 > wall[0] and x - 15 < wall[0] + wall[2] and y + 15 > wall[1] and y - 15 < wall[1] + wall[3]):
                    valid = False; break
            if valid: return x, y
            attempts += 1
        return (random.randint(self.play_area.left, self.play_area.right), random.randint(self.play_area.top, self.play_area.bottom))
    
    def spawn_zombies(self, count):
        for _ in range(count):
            x, y = self.get_valid_zombie_spawn_point()
            base_difficulty = min(5, max(1, (self.generation // 5) + 1))
            wave_multiplier = 1 + (self.wave_number - 1) * 0.2
            difficulty_multiplier = {'easy': 0.8, 'normal': 1.0, 'hard': 1.3, 'insane': 1.8}[self.current_difficulty]
            difficulty = int(base_difficulty * wave_multiplier * difficulty_multiplier)
            difficulty = max(1, min(8, difficulty))
            self.zombies.append(Zombie(x, y, difficulty))
    
    def start_wave(self):
        self.wave_in_progress = True
        self.wave_cooldown = 0
        base_size = self.base_wave_size
        wave_growth = 5 * (self.wave_number - 1)
        gen_growth = self.generation // 2
        total_zombies = min(base_size + wave_growth + gen_growth, self.max_zombies // 2)
        self.zombies_to_spawn = total_zombies
        print(f"🚀 Début de la vague {self.wave_number} : {total_zombies} zombies à spawner")
    
    def spawn_ammo(self, count=1):
        for _ in range(count):
            attempts = 0
            while attempts < 100:
                x = random.randint(self.play_area.left + 30, self.play_area.right - 30)
                y = random.randint(self.play_area.top + 30, self.play_area.bottom - 30)
                valid = True
                for wall in self.walls:
                    if (x + 20 > wall[0] and x - 20 < wall[0] + wall[2] and y + 20 > wall[1] and y - 20 < wall[1] + wall[3]):
                        valid = False; break
                if valid:
                    too_close = False
                    for ammo in self.ammo_packs:
                        if math.sqrt((x - ammo.x)**2 + (y - ammo.y)**2) < 40: too_close = True; break
                    if not too_close:
                        self.ammo_packs.append(AmmoPack(x, y))
                        break
                attempts += 1
    
    def update(self):
        if self.paused: return
        self.game_time += 1
        for ammo in self.ammo_packs: ammo.update()
        
        for human in self.humans:
            if human.alive:
                bullet = human.update(self.zombies, self.ammo_packs, self.walls)
                if bullet:
                    self.bullets.append(bullet)
                    if not hasattr(human, 'ammo_used'): human.ammo_used = 0
                    human.ammo_used += 1
        
        for zombie in self.zombies:
            if zombie.alive:
                target = zombie.update(self.humans, self.walls)
                if target: target.take_damage(zombie.damage)
        
        for bullet in self.bullets[:]:
            bullet.update(self.walls)
            for zombie in self.zombies[:]:
                if (zombie.alive and math.sqrt((bullet.x - zombie.x)**2 + (bullet.y - zombie.y)**2) < bullet.radius + zombie.radius):
                    if zombie.take_damage(bullet.damage):
                        self.zombies_killed_this_gen += 1
                        self.total_kills += 1
                        closest_human = None
                        min_dist = float('inf')
                        for human in self.humans:
                            if human.alive:
                                dist = math.sqrt((human.x - zombie.x)**2 + (human.y - zombie.y)**2)
                                if dist < min_dist and dist < 200:
                                    min_dist = dist
                                    closest_human = human
                        if closest_human: closest_human.kills += 1
                    bullet.alive = False
                    break
            if not bullet.alive: self.bullets.remove(bullet)
        
        self.humans = [h for h in self.humans if h.alive]
        self.zombies = [z for z in self.zombies if z.alive]
        
        if self.wave_in_progress:
            if self.zombies_to_spawn > 0:
                self.zombie_spawn_timer -= 1
                if self.zombie_spawn_timer <= 0:
                    zombies_alive = len(self.zombies)
                    if zombies_alive < self.max_zombies:
                        spawn_group = min(3, self.zombies_to_spawn, self.max_zombies - zombies_alive)
                        if spawn_group > 0:
                            self.spawn_zombies(spawn_group)
                            self.zombies_to_spawn -= spawn_group
                            self.zombie_spawn_timer = max(10, self.zombie_spawn_rate // 2)
            else:
                if len(self.zombies) == 0:
                    self.wave_in_progress = False
                    self.wave_cooldown = 180
                    print(f"✅ Vague {self.wave_number} terminée!")
        elif self.wave_cooldown > 0:
            self.wave_cooldown -= 1
            if self.wave_cooldown <= 0:
                self.wave_number += 1
                self.start_wave()
        
        self.ammo_spawn_timer -= 1
        if self.ammo_spawn_timer <= 0 and len(self.ammo_packs) < 8:
            self.spawn_ammo(1)
            self.ammo_spawn_timer = 150
        
        if self.auto_next_gen and all(not human.alive for human in self.humans) and len(self.humans) > 0:
            self.next_generation()
    
    def next_generation(self):
        new_chromosomes = self.ga.create_new_generation(self.humans, self.generation)
        if self.humans:
            fitness_values = [h.fitness for h in self.humans if h.alive]
            if fitness_values:
                self.best_fitness_history.append(max(fitness_values))
                self.average_fitness_history.append(sum(fitness_values) / len(fitness_values))
        
        self.humans = []; self.bullets = []; self.ammo_packs = []; self.zombies = []
        self.zombie_spawn_timer = 0; self.ammo_spawn_timer = 0; self.zombies_killed_this_gen = 0
        self.wave_number = 1; self.wave_in_progress = False; self.wave_cooldown = 0
        
        spawn_points = self.get_valid_spawn_points(len(new_chromosomes))
        for i, chromosome in enumerate(new_chromosomes):
            if i < len(spawn_points): x, y = spawn_points[i]
            else: x, y = random.randint(self.play_area.left + 30, self.play_area.right - 30), random.randint(self.play_area.top + 30, self.play_area.bottom - 30)
            human = Human(x, y, chromosome, self.generation + 1)
            human.ammo_used = 0
            self.humans.append(human)
        
        self.start_wave()
        self.generation += 1
        print(f"Génération {self.generation} créée!")
    
    def draw_evolution_graph(self, surface, x, y, width, height):
        if len(self.best_fitness_history) < 2: return
        pygame.draw.rect(surface, (30, 30, 60), (x, y, width, height))
        pygame.draw.rect(surface, (50, 50, 90), (x, y, width, height), 2)
        grid_steps = 5
        for i in range(1, grid_steps):
            grid_y = y + height - (i * height / grid_steps)
            pygame.draw.line(surface, GRID_COLOR, (x, grid_y), (x + width, grid_y), 1)
        max_fitness = max(self.best_fitness_history)
        scale_factor = height / (max_fitness * 1.1)
        
        points_best = []
        for i, fitness in enumerate(self.best_fitness_history):
            px = x + (i * width / max(1, len(self.best_fitness_history) - 1))
            py = y + height - (fitness * scale_factor)
            points_best.append((px, py))
        if len(points_best) > 1: pygame.draw.lines(surface, (255, 100, 100), False, points_best, 3)
        
        if len(self.average_fitness_history) > 1:
            points_avg = []
            for i, fitness in enumerate(self.average_fitness_history):
                px = x + (i * width / max(1, len(self.average_fitness_history) - 1))
                py = y + height - (fitness * scale_factor)
                points_avg.append((px, py))
            pygame.draw.lines(surface, (100, 200, 255), False, points_avg, 2)
        
        legend_y = y + 10
        pygame.draw.line(surface, (255, 100, 100), (x + 10, legend_y), (x + 30, legend_y), 3)
        surface.blit(self.small_font.render("Meilleure fitness", True, TEXT_COLOR), (x + 35, legend_y - 8))
        if len(self.average_fitness_history) > 1:
            pygame.draw.line(surface, (100, 200, 255), (x + 10, legend_y + 20), (x + 30, legend_y + 20), 2)
            surface.blit(self.small_font.render("Fitness moyenne", True, TEXT_COLOR), (x + 35, legend_y + 12))
        title = self.font.render("Évolution de la Fitness", True, (255, 255, 200))
        surface.blit(title, (x + width//2 - title.get_width()//2, y - 30))
    
    def draw_ui(self):
        ui_height = 200 if self.show_stats else 120
        ui_surface = pygame.Surface((SCREEN_WIDTH, ui_height), pygame.SRCALPHA)
        ui_surface.fill(UI_BG); self.screen.blit(ui_surface, (0, 0))
        
        humans_alive = len([h for h in self.humans if h.alive])
        main_stats = [f"GÉNÉRATION: {self.generation}", f"VAGUE: {self.wave_number}", f"HUMAINS: {humans_alive}/{len(self.humans)}",
                      f"ZOMBIES: {len(self.zombies)}/{self.max_zombies}", f"ZOMBIES TUÉS: {self.zombies_killed_this_gen}",
                      f"DIFFICULTÉ: {self.current_difficulty.upper()}"]
        for i, text in enumerate(main_stats):
            color = (255, 200, 100) if i == 0 else TEXT_COLOR
            self.screen.blit(self.font.render(text, True, color), (20, 20 + i * 28))
        
        wave_text = f"Zombies restants: {self.zombies_to_spawn}" if self.wave_in_progress else f"Prochaine vague dans: {self.wave_cooldown//60}s" if self.wave_cooldown > 0 else "Préparation..."
        self.screen.blit(self.font.render(wave_text, True, (255, 150, 150)), (SCREEN_WIDTH - 250, 20))
        
        button_color = (80, 180, 80) if self.next_gen_button.collidepoint(pygame.mouse.get_pos()) else (60, 160, 60)
        pygame.draw.rect(self.screen, button_color, self.next_gen_button, border_radius=8)
        pygame.draw.rect(self.screen, (100, 220, 100), self.next_gen_button, 3, border_radius=8)
        next_gen_text = self.font.render("NOUVELLE GÉNÉRATION", True, (255, 255, 255))
        self.screen.blit(next_gen_text, next_gen_text.get_rect(center=self.next_gen_button.center))
        
        pause_color = (180, 80, 80) if self.pause_button.collidepoint(pygame.mouse.get_pos()) else (160, 60, 60)
        pygame.draw.rect(self.screen, pause_color, self.pause_button, border_radius=8)
        pygame.draw.rect(self.screen, (220, 100, 100), self.pause_button, 3, border_radius=8)
        pause_text_surf = self.font.render("REPRENDRE" if self.paused else "PAUSE", True, (255, 255, 255))
        self.screen.blit(pause_text_surf, pause_text_surf.get_rect(center=self.pause_button.center))
        
        for diff, rect in self.difficulty_buttons.items():
            if diff == self.current_difficulty:
                color = (100, 200, 100) if diff == 'easy' else (200, 200, 100) if diff == 'normal' else (200, 150, 50) if diff == 'hard' else (200, 50, 50)
            else:
                color = (60, 140, 60) if diff == 'easy' else (140, 140, 60) if diff == 'normal' else (140, 100, 30) if diff == 'hard' else (140, 30, 30)
            if rect.collidepoint(pygame.mouse.get_pos()): color = tuple(min(255, c + 40) for c in color)
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, (220, 220, 220), rect, 2, border_radius=5)
            diff_text = self.small_font.render(diff.upper(), True, (255, 255, 255))
            self.screen.blit(diff_text, diff_text.get_rect(center=rect.center))
        
        instructions = ["CLIC sur le bouton pour nouvelle génération", "ESPACE: Mode auto-génération", "1-4: Changer difficulté", "V: Afficher champs de vision", "R: Réinitialiser simulation"]
        for i, text in enumerate(instructions): self.screen.blit(self.small_font.render(text, True, (200, 200, 200)), (SCREEN_WIDTH - 320, 50 + i * 22))
        
        if self.show_stats and humans_alive > 0:
            alive_humans = [h for h in self.humans if h.alive]
            if alive_humans:
                best_human = max(alive_humans, key=lambda h: h.fitness)
                stats_bg = pygame.Surface((350, 140), pygame.SRCALPHA); stats_bg.fill((40, 40, 80, 200))
                self.screen.blit(stats_bg, (SCREEN_WIDTH // 2 - 175, 30))
                best_title = self.font.render(f"MEILLEUR SURVIVANT (G{best_human.generation})", True, (255, 220, 100))
                self.screen.blit(best_title, (SCREEN_WIDTH // 2 - best_title.get_width()//2, 35))
                best_stats = [f"Vitesse: {best_human.speed:.2f}", f"Vision: {best_human.vision:.0f}", f"Précision: {best_human.accuracy:.2f}",
                              f"Agressivité: {best_human.aggressiveness:.2f}", f"Kills: {best_human.kills}", f"Fitness: {best_human.fitness:.1f}"]
                for i, text in enumerate(best_stats[:3]): self.screen.blit(self.small_font.render(text, True, TEXT_COLOR), (SCREEN_WIDTH // 2 - 160, 70 + i * 22))
                for i, text in enumerate(best_stats[3:]): self.screen.blit(self.small_font.render(text, True, TEXT_COLOR), (SCREEN_WIDTH // 2, 70 + i * 22))
                if len(self.best_fitness_history) > 1: self.draw_evolution_graph(self.screen, SCREEN_WIDTH - 420, SCREEN_HEIGHT - 250, 400, 200)
    
    def draw(self):
        self.screen.fill(BACKGROUND)
        grid_size = 40
        for x in range(0, SCREEN_WIDTH, grid_size): pygame.draw.line(self.screen, GRID_COLOR, (x, 0), (x, SCREEN_HEIGHT), 1)
        for y in range(0, SCREEN_HEIGHT, grid_size): pygame.draw.line(self.screen, GRID_COLOR, (0, y), (SCREEN_WIDTH, y), 1)
        for wall in self.walls: pygame.draw.rect(self.screen, (90, 90, 120), wall); pygame.draw.rect(self.screen, (70, 70, 100), wall, 3)
        for ammo in self.ammo_packs: ammo.draw(self.screen)
        for bullet in self.bullets: bullet.draw(self.screen)
        for zombie in self.zombies: zombie.draw(self.screen)
        for human in self.humans: human.draw(self.screen, self.show_vision)
        self.draw_ui()
        if self.paused:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA); overlay.fill((0, 0, 0, 128)); self.screen.blit(overlay, (0, 0))
            pause_text = self.big_font.render("PAUSE", True, (255, 80, 80))
            self.screen.blit(pause_text, pause_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)))
        if self.auto_next_gen:
            auto_text = self.font.render("MODE AUTO-GÉNÉRATION ACTIF", True, (255, 200, 100))
            self.screen.blit(auto_text, (SCREEN_WIDTH//2 - auto_text.get_width()//2, SCREEN_HEIGHT - 40))
        if len(self.zombies) > 20:
            zombie_count_text = self.big_font.render(f"ZOMBIES: {len(self.zombies)}", True, (255, 50, 50))
            self.screen.blit(zombie_count_text, (SCREEN_WIDTH//2 - zombie_count_text.get_width()//2, 50))
        pygame.display.flip()
    
    def handle_click(self, pos):
        if self.next_gen_button.collidepoint(pos): self.next_generation(); return True
        if self.pause_button.collidepoint(pos): self.paused = not self.paused; return True
        for diff, rect in self.difficulty_buttons.items():
            if rect.collidepoint(pos): self.change_difficulty(diff); return True
        return False
    
    def change_difficulty(self, difficulty):
        if difficulty in self.difficulty_settings:
            self.current_difficulty = difficulty
            self.apply_difficulty_settings()
            print(f"Difficulté changée: {difficulty.upper()}")
    
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1: self.handle_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p: self.paused = not self.paused
                    elif event.key == pygame.K_r: self.__init__()
                    elif event.key == pygame.K_v: self.show_vision = not self.show_vision
                    elif event.key == pygame.K_SPACE: self.auto_next_gen = not self.auto_next_gen
                    elif event.key == pygame.K_s: self.show_stats = not self.show_stats
                    elif event.key == pygame.K_1 or event.key == pygame.K_KP1: self.change_difficulty('easy')
                    elif event.key == pygame.K_2 or event.key == pygame.K_KP2: self.change_difficulty('normal')
                    elif event.key == pygame.K_3 or event.key == pygame.K_KP3: self.change_difficulty('hard')
                    elif event.key == pygame.K_4 or event.key == pygame.K_KP4: self.change_difficulty('insane')
                    elif event.key == pygame.K_PLUS or event.key == pygame.K_KP_PLUS: self.spawn_zombies(10)
                    elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS: self.spawn_zombies(5)
            if not self.paused: self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()