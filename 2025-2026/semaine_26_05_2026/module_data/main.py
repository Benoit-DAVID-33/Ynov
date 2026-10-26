from pathlib import Path
from sklearn.preprocessing import LabelEncoder

from custom_image_dataset import CustomImageDataset
from custom_labelled_image_dataset import CustomLabelledImageDataset
from dataloader import my_custom_generator, CustomDataLoader

DATA_DIR = Path("./image_dataset/flower_photos")
CLASSES = ["daisy", "dandelion", "roses", "sunflowers", "tulips"]

# --- Récupération des chemins d'images ---
image_paths = []
for cls in CLASSES:
    image_paths.extend((DATA_DIR / cls).glob("*.jpg"))

print(f"Nombre d'images : {len(image_paths)}")

# --- Test CustomImageDataset ---
print("\n--- CustomImageDataset ---")
dataset = CustomImageDataset(image_paths)
print(f"Taille du dataset : {len(dataset)}")
img = dataset[0]
print(f"Shape de la première image : {img.shape}")

# --- Test CustomLabelledImageDataset ---
print("\n--- CustomLabelledImageDataset ---")
label_mapping = {}
for cls in CLASSES:
    for path in (DATA_DIR / cls).glob("*.jpg"):
        label_mapping[path] = cls

labelled_dataset = CustomLabelledImageDataset(label_mapping)
img, label = labelled_dataset[0]
print(f"Shape image : {img.shape}, label : {label}")

# --- Test avec LabelEncoder ---
print("\n--- CustomLabelledImageDataset avec LabelEncoder ---")
le = LabelEncoder()
le.fit(CLASSES)
encoded_dataset = CustomLabelledImageDataset(label_mapping, target_transform=le)
img, label = encoded_dataset[0]
print(f"Shape image : {img.shape}, label encodé : {label}")

# --- Test générateur ---
print("\n--- Générateur (batch_size=32) ---")
for i, batch in enumerate(my_custom_generator(dataset, batch_size=32)):
    print(f"Batch {i} : shape={batch.shape}")
    if i == 2:
        break

# --- Test CustomDataLoader ---
print("\n--- CustomDataLoader (batch_size=32) ---")
loader = CustomDataLoader(labelled_dataset, batch_size=32, shuffle=True)
print(f"Nombre de batches : {len(loader)}")
for i, (images, labels) in enumerate(loader):
    print(f"Batch {i} : images={images.shape}, labels={labels.shape}")
    if i == 2:
        break
