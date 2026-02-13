import os
import nltk  # We still need this for the setup

# Stay within utils directory
utils_dir = os.path.dirname(os.path.abspath(__file__))
nltk_data_dir = os.path.join(utils_dir, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)

# Configure NLTK to use this directory
nltk.data.path.insert(0, nltk_data_dir)

# Download required packages
required_packages = [
    'punkt',
    'averaged_perceptron_tagger',
    'wordnet'
]

for package in required_packages:
    try:
        nltk.data.find(f'tokenizers/{package}')
        print(f"{package} already downloaded")
    except LookupError:
        print(f"Downloading {package}")
        nltk.download(package, download_dir=nltk_data_dir)