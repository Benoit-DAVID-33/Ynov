from custom_image_dataset import CustomImageDataset


class CustomLabelledImageDataset(CustomImageDataset):
    def __init__(self, label_mapping, transform=None, target_transform=None):
        super().__init__(list(label_mapping.keys()), transform)
        self.label_mapping = label_mapping
        self.target_transform = target_transform

    def __getitem__(self, idx):
        image = super().__getitem__(idx)
        label = self.label_mapping[self.image_paths[idx]]
        if self.target_transform is not None:
            label = self.target_transform.transform([label])[0]
        return image, label
