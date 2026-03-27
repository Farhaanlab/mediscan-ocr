import os
import json
import io
import re
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image
import pytesseract
import cv2
import numpy as np
import spacy

from matcher import match_medicines

# ---------------------------------------------------------
# IMPORTANT: Update this path if Tesseract is installed elsewhere.
# Default Windows installation path:
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# ---------------------------------------------------------

app = FastAPI(title="Prescription Scanner API (Local)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Attempt to load SpaCy English model for NLP
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading English model for SpaCy...")
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")


def preprocess_image(image_bytes):
    """
    Standard OpenCV pipeline to clean up an image for OCR.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Resize to improve OCR (scale up 2x)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # Denoising
    denoised = cv2.fastNlMeansDenoising(gray, h=30)
    
    # Thresholding to get crisp black text on white background
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    return Image.fromarray(thresh)


def extract_potential_medicines(text):
    """
    Given raw OCR text, extract lines that look like medicine names.
     specifically for tabular prescriptions.
    """
    lines = text.split('\n')
    candidates = []
    
    # Common terms in prescriptions we want to ignore entirely
    ignore_words = {'dr', 'doctor', 'clinic', 'hospital', 'patient', 'name', 'date', 'age', 'sex', 'male', 'female', 'signature', 'tab', 'cap', 'syr', 'mg', 'ml', 'rx', 'hourly', 'times', 'week', 'days', 'month', 'drop', 'alternate', 'nights', 'continue', 'till', 'over', 'sos', 'post', 'operative', 'medications', 'eye', 'drops', 'left', 'right', 'tablets', 'syrup', 'capsules'}
    
    for line in lines:
        clean_line = line.strip()
        # Remove anything before the first letter to get rid of completely broken numbers
        # e.g "1. MILFLODEX E/d" -> "MILFLODEX E/d"
        clean_line = re.sub(r'^[^a-zA-Z]+', '', clean_line)
        
        # Keep letters, numbers, spaces, dots, hyphens (and slashes since E/d is common)
        clean_line = re.sub(r'[^a-zA-Z0-9\s\.\-/]', '', clean_line).strip()
        
        # Remove common dosage patterns directly using regex
        # e.g. "1 hourly", "2 times", "* 1 week", "2 months"
        clean_line = re.sub(r'\b\d+\s*(hourly|times|week|days|month|months|drop|drops)\b', '', clean_line, flags=re.IGNORECASE)
        # e.g "22.07.2025"
        clean_line = re.sub(r'\b\d{2}\.\d{2}\.\d{4}\b', '', clean_line)
        # remove standalone numbers
        clean_line = re.sub(r'\b\d+\b', '', clean_line)
        
        # After removing noise, clean it again
        clean_line = clean_line.strip()
        
        # Length check
        if len(clean_line) < 4 or len(clean_line) > 50:
            continue
            
        lower_line = clean_line.lower()
        words = set(lower_line.split())
        
        # If the line is EXACTLY an ignore word or contains mostly ignore words, skip
        if words.intersection(ignore_words) and len(words) <= 2:
            continue
            
        # Use spacy to filter out standard English words (verbs, common nouns)
        # We want proper nouns or unknown words (medicines)
        doc = nlp(clean_line)
        is_valuable = False
        for token in doc:
            if token.pos_ in ['PROPN', 'NOUN', 'X'] or not token.is_oov:
                # If there's a proper noun/noun or an out-of-vocabulary word (like 'Crocin'), keep it
                is_valuable = True
                break
                
        if is_valuable:
             # Further clean specific common medical abbreviations often attached to titles
             # E/d -> Eye drop, T. -> Tablet, C. -> Capsule
             clean_line = re.sub(r'\bE/d\b', '', clean_line, flags=re.IGNORECASE).strip()
             clean_line = re.sub(r'^T\.', '', clean_line, flags=re.IGNORECASE).strip()
             clean_line = re.sub(r'^C\.', '', clean_line, flags=re.IGNORECASE).strip()
             clean_line = re.sub(r'\s-\s.*', '', clean_line).strip() # Removes trailing dashed stuff like "- O"
             
             if len(clean_line) >= 4:
                 candidates.append(clean_line)
        
    # Return unique items
    return list(dict.fromkeys(candidates))


@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/scan")
async def scan_prescription(file: UploadFile = File(...)):
    contents = await file.read()
    
    try:
        # 1. Preprocess the image
        processed_image = preprocess_image(contents)
        
        # 2. Run Tesseract OCR
        # --psm 4 assumes a single column of text of variable sizes
        # --psm 6 assumes a single uniform block of text
        # --psm 3 or 4 or 6 are common. Given the tabular nature of the image, --psm 4 or 6 are great.
        raw_text = pytesseract.image_to_string(processed_image, config='--psm 6')
        print(f"------------\nRaw Tesseract Extracted Text:\n{raw_text}\n------------")
        
        # 3. Filter the text to find potential medicine names
        potential_names = extract_potential_medicines(raw_text)
        print(f"Filtered Candidates: {potential_names}")
        
        if not potential_names:
            summary = raw_text.replace('\n', ' ')[:50]
            summary = summary if summary else "No readable text"
            return {
                "extracted_raw": [f"Raw OCR snippet: {summary}..."],
                "medicines": []
            }
            
        # 4. Match against dataset
        results = match_medicines(potential_names)
        
        # Filter out errors/non-matches since local OCR produces a lot of noise
        valid_results = [r for r in results if r.get('matched_name')]
        
        return {
            "extracted_raw": potential_names,
            "medicines": valid_results
        }
        
    except Exception as e:
        print(f"Error during scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))
