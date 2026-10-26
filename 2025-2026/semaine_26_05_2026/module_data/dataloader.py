import numpy as np
import random


def my_custom_generator(dataset, batch_size, shuffle=False):
    indices = list(range(len(dataset)))
    if shuffle:
        random.shuffle(indices)
    for i in range(0, len(indices), batch_size):
        batch_indices = indices[i:i + batch_size]
        batch = [dataset[idx] for idx in batch_indices]
        if isinstance(batch[0], tuple):
            images = np.array([b[0] for b in batch])
            labels = np.array([b[1] for b in batch])
            yield images, labels
        else:
            yield np.array(batch)


class CustomDataLoader:
    def __init__(self, dataset, batch_size, shuffle=False):
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        self._indices = []
        self._current = 0

    def __len__(self):
        return (len(self.dataset) + self.batch_size - 1) // self.batch_size

    def __iter__(self):
        self._indices = list(range(len(self.dataset)))
        if self.shuffle:
            random.shuffle(self._indices)
        self._current = 0
        return self

    def __next__(self):
        if self._current >= len(self.dataset):
            raise StopIteration
        batch_indices = self._indices[self._current:self._current + self.batch_size]
        self._current += self.batch_size
        batch = [self.dataset[idx] for idx in batch_indices]
        if isinstance(batch[0], tuple):
            images = np.array([b[0] for b in batch])
            labels = np.array([b[1] for b in batch])
            return images, labels
        return np.array(batch)
