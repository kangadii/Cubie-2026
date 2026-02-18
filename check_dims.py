import numpy as np

try:
    data = np.load('help_embeddings.npz', allow_pickle=True)
    embeddings = data['embeddings']
    print(f"Stored embeddings shape: {embeddings.shape}")
    if len(embeddings) > 0:
        print(f"Single embedding size: {len(embeddings[0])}")
    else:
        print("No embeddings found.")
except Exception as e:
    print(f"Error loading embeddings: {e}")
