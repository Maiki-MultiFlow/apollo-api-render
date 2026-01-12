# Use Python 3.11 slim to avoid Pydantic Rust build issues
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Set environment variable for uvicorn to use the correct host/port
ENV PORT 10000

# Start command for FastAPI using the assigned PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
