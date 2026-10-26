import numpy as np
import cv2

IMG_SIZE = (128, 128)


class CustomImageDataset:
    def __init__(self, image_paths, transform=None):
        self.image_paths = image_paths
        self.transform = transform

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        image = cv2.imread(str(self.image_paths[idx]))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, IMG_SIZE)
        if self.transform is not None:
            image = self.transform(image=image)["image"]
        return image
