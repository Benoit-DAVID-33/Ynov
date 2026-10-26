# game.py
import random
import pygame
from config import *

class Game:
    def __init__(self, snake):
        self.snake = snake
        self.food = self.spawn_food()

    def spawn_food(self):
        while True:
            p = (random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1))
            if p not in self.snake.positions:
                return p

    def update(self):
        self.snake.think(self.food)
        if self.snake.move(self.food):
            self.food = self.spawn_food()

    def draw(self, screen):
        screen.fill(BLACK)

        for x, y in self.snake.positions:
            pygame.draw.rect(
                screen, GREEN,
                (x*GRID_SIZE, y*GRID_SIZE, GRID_SIZE, GRID_SIZE)
            )

        fx, fy = self.food
        pygame.draw.rect(
            screen, RED,
            (fx*GRID_SIZE, fy*GRID_SIZE, GRID_SIZE, GRID_SIZE)
        )
