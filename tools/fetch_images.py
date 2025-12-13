import os
import requests
import re
import time

# Create docs/images directory if it doesn't exist
OUTPUT_DIR = os.path.join("docs", "images")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Image Mapping (using Apple CDN or Placeholders)
# Note: For unreleased/future models (iPhone 17, Air, 16e), we will use placeholders or previous model images as proxies if not available.
# Since this is a demo/dev environment, I will use high-quality placeholders or known URLs where possible.

# Helper to get Apple CDN URL for existing models
def get_apple_url(model_slug, color_slug):
    # This is a heuristic, URLs change often. Using the user provided ones as base.
    return f"https://store.storeimages.cdn-apple.com/4668/as-images.apple.com/is/{model_slug}-{color_slug}-select-202309"  # approximate

image_map = {
    # 16 Series
    "iPhone 16": "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-16-ultramarine-select-202409?wid=470&hei=556&fmt=png-alpha&.v=1723227181822",
    "iPhone 16 Plus": "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-16-plus-pink-select-202409?wid=470&hei=556&fmt=png-alpha&.v=1723227148964",
    # Pro/Max often have expiring URLs, using placeholders for reliability in this demo
    "iPhone 16 Pro": "https://placehold.co/400x500/png?text=iPhone+16+Pro",
    "iPhone 16 Pro Max": "https://placehold.co/400x500/png?text=iPhone+16+Pro+Max",
    
    # 16e (Hypothetical/New)
    "iPhone 16e": "https://placehold.co/400x500/png?text=iPhone+16e",

    # 15 Series
    "iPhone 15": "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-15-blue-select-202309?wid=470&hei=556&fmt=png-alpha",
    "iPhone 15 Pro": "https://placehold.co/400x500/png?text=iPhone+15+Pro",
    "iPhone 15 Pro Max": "https://placehold.co/400x500/png?text=iPhone+15+Pro+Max",
    
    # SE
    "iPhone SE (第3世代)": "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-se-midnight-select-202203?wid=470&hei=556&fmt=png-alpha",
    "iPhone SE（第3世代）": "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-se-midnight-select-202203?wid=470&hei=556&fmt=png-alpha",

    # 17 / future (Placeholders)
    "iPhone 17": "https://placehold.co/400x500/png?text=iPhone+17",
    "iPhone 17 Pro": "https://placehold.co/400x500/png?text=iPhone+17+Pro",
    "iPhone 17 Pro Max": "https://placehold.co/400x500/png?text=iPhone+17+Pro+Max",
    "iPhone Air": "https://placehold.co/400x500/png?text=iPhone+Air",
}

def normalize_model_name(name):
    """
    Converts model name to filesystem safe slug:
    'iPhone 16 Pro' -> 'iphone16pro'
    'iPhone SE (第3世代)' -> 'iphonese3' (special handling) or 'iphonese'
    """
    clean = name.lower()
    # Replace common patterns
    if 'se' in clean and ('3' in clean or '第3' in clean):
         return 'iphonese3'
    
    # Keep only a-z and 0-9
    clean = re.sub(r'[^a-z0-9]', '', clean)
    return clean

def download_image(url, filename, save_path):
    print(f"Downloading {filename} from {url}...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Saved to {save_path}")
        return True
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
        return False

def main():
    for model_name, url in image_map.items():
        # Generate filename
        # Special handling for SE to ensure consistency if needed, but regex above handles it
        slug = normalize_model_name(model_name)
        
        # If duplicated keys in normalize (e.g. SE half/full width), it's fine, we iterate map
        filename = f"{slug}.png"
        save_path = os.path.join(OUTPUT_DIR, filename)
        
        if os.path.exists(save_path):
            print(f"Skipping {filename}, already exists.")
            continue
            
        success = download_image(url, filename, save_path)
        if success:
            time.sleep(1) # Be nice to server for batch downloads

if __name__ == "__main__":
    main()
