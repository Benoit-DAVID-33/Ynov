# main.py
import pygame
from config import *
from genetic_algorithm import GeneticAlgorithm
from game import Game
from utils import plot_fitness

def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    ga = GeneticAlgorithm()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        snake = ga.population[0]
        game = Game(snake)

        while snake.alive:
            game.update()
            game.draw(screen)
            pygame.display.flip()
            clock.tick(FPS)

        ga.evaluate()
        selected = ga.select()
        ga.reproduce(selected)

    plot_fitness(ga.history)
    pygame.quit()

if __name__ == "__main__":
    main()
