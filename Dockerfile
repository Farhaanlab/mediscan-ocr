# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install system dependencies for OpenCV and Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download the SpaCy model required by the app
RUN python -m spacy download en_core_web_sm

# Copy the rest of the application code
COPY . .

# Expose the correct port (Render dynamically assigns $PORT)
EXPOSE 8085

# Start the Fast API app securely
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8085}"]
