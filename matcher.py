import pandas as pd
from thefuzz import process, fuzz
import os
import math

DATASET_PATH = "A_Z_medicines_dataset_of_India.csv"

# Load the dataset globally so it's only loaded once when the application starts
try:
    df = pd.read_csv(DATASET_PATH)
    # Create a list of all medicine names for faster fuzzy matching
    # We maintain a tuple of (Original Name, Search Name) to help matching
    all_medicine_names = df['name'].fillna('').astype(str).tolist()
    
    # We'll create a dictionary for fast lookup of original names by lowercase names
    # and a separate list for thefuzz to search against
    search_medicines = {i: str(n).lower() for i, n in enumerate(all_medicine_names)}
    
    print(f"Loaded {len(all_medicine_names)} medicines from dataset.")
except Exception as e:
    print(f"Failed to load dataset: {e}")
    df = None
    all_medicine_names = []
    search_medicines = {}

def get_val(val):
    if pd.isna(val):
        return "N/A"
    if isinstance(val, float) and math.isnan(val):
        return "N/A"
    return str(val)

def custom_scorer(query, choice):
    """
    A custom scorer for local OCR.
    Local OCR often gets the beginning of the word right but messes up the end or appends noise.
    """
    # Base fuzziness
    base_score = fuzz.token_set_ratio(query, choice)
    
    # Boost score if the query starts with the exact same 4-5 letters as the choice
    # e.g., "MILFLODEX E/d" vs "Milflodex (Eye drop)"
    q_words = query.split()
    c_words = choice.split()
    
    if q_words and c_words:
        first_q = q_words[0][:5]
        first_c = c_words[0][:5]
        if len(first_q) >= 4 and first_q == first_c:
            base_score += 15  # Big boost for matching prefixes
            
    return min(100, base_score)

def match_medicines(extracted_names):
    results = []
    if df is None or not all_medicine_names:
        for name in extracted_names:
            results.append({
                "extracted_name": name,
                "error": "Dataset not loaded"
            })
        return results
        
    for name in extracted_names:
        clean_name = str(name).strip().lower()
        if len(clean_name) < 4:  # Very short strings usually OCR errors
            continue
            
        # Find the best match using our custom scorer
        best_match = process.extractOne(clean_name, search_medicines, scorer=custom_scorer)
        
        if best_match:
            # best_match[0] is the lowercase search name, best_match[2] is the index
            matched_index = best_match[2]
            original_matched_name = all_medicine_names[matched_index]
            score = best_match[1]
            
            # Since local OCR is messy, we lower the threshold compared to Gemini's clean output
            # A score > 65 with our boosted token_set_ratio usually indicates a reasonable partial match
            if score > 65:
                # Find all exact matches for this name and take the first
                row = df.iloc[matched_index]
                
                comp1 = get_val(row['short_composition1'])
                comp2 = get_val(row.get('short_composition2', 'N/A'))
                composition = comp1
                if comp2 != "N/A":
                    composition += f" + {comp2}"
                    
                results.append({
                    "extracted_name": name,
                    "matched_name": original_matched_name,
                    "match_score": score,
                    "price": get_val(row['price(₹)']),
                    "manufacturer": get_val(row['manufacturer_name']),
                    "type": get_val(row['type']),
                    "pack_size": get_val(row['pack_size_label']),
                    "composition": composition
                })
            else:
                results.append({
                    "extracted_name": name,
                    "matched_name": None,
                    "match_score": score,
                    "error": "No confident match found in dataset"
                })
                
    return results
