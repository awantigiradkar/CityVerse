import os
import pickle
from typing import Any

# Resolve absolute path to 'models' directory in project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, "models")

def save_model(model: Any, task_name: str):
    """
    Saves a trained model binary to the registry folder.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    file_path = os.path.join(MODELS_DIR, f"{task_name}_model.pkl")
    with open(file_path, "wb") as f:
        pickle.dump(model, f)
    print(f"Successfully registered model: {file_path}")

def load_model(task_name: str) -> Any:
    """
    Loads a model binary from the registry folder.
    """
    file_path = os.path.join(MODELS_DIR, f"{task_name}_model.pkl")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No model found for task '{task_name}' in registry: {file_path}")
    with open(file_path, "rb") as f:
        model = pickle.load(f)
    return model