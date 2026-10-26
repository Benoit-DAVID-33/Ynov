import numpy as np
import copy

def relu(x):
    return np.maximum(0, x)

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

class NeuralNetwork:
    def __init__(self, input_size=12, hidden_size=16, output_size=4):
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size

        self.W1 = np.random.uniform(-1, 1, (input_size, hidden_size))
        self.B1 = np.random.uniform(-1, 1, (1, hidden_size))
        
        self.W2 = np.random.uniform(-1, 1, (hidden_size, output_size))
        self.B2 = np.random.uniform(-1, 1, (1, output_size))

    def forward(self, x):
        
        x = np.array(x).reshape(1, -1)
        self.z1 = np.dot(x, self.W1) + self.B1
        self.a1 = relu(self.z1)
        
        # Z2 = Activations1 * Poids2 + Biais2
        self.z2 = np.dot(self.a1, self.W2) + self.B2
        output = sigmoid(self.z2)
        
        return output.flatten()

    def mutate(self, rate=0.05, intensity=0.2):
        params = [self.W1, self.B1, self.W2, self.B2]
        
        for p in params:
            mutation_mask = np.random.rand(*p.shape) < rate
            
            noise = np.random.normal(0, intensity, size=p.shape)
            p += mutation_mask * noise

    @staticmethod
    def crossover(net1, net2):
        child = NeuralNetwork(net1.input_size, net1.hidden_size, net1.output_size)
        
        # Liste des paramètres des parents et de l'enfant
        params1 = [net1.W1, net1.B1, net1.W2, net1.B2]
        params2 = [net2.W1, net2.B1, net2.W2, net2.B2]
        child_params = [child.W1, child.B1, child.W2, child.B2]
        
        for p1, p2, pc in zip(params1, params2, child_params):
            
            pc[:] = np.where(mask, p1, p2)
            
        return child