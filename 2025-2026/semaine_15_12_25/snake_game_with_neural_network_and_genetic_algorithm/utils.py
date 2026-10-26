# utils.py
import matplotlib.pyplot as plt

def plot_fitness(history):
    plt.plot(history)
    plt.title("Fitness par génération")
    plt.xlabel("Génération")
    plt.ylabel("Fitness")
    plt.grid()
    plt.show()
