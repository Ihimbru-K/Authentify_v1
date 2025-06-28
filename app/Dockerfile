# Use a lightweight Python 3.11 image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /Authentikate

# Copy requirements.txt first to cache dependencies
COPY requirements.txt .

# Install dependencies and clean up
RUN apt-get update && apt-get install -y libpq-dev gcc && apt-get clean
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Expose port (Railway assigns PORT dynamically, but this is for clarity)
EXPOSE 8000

# Set default port (Railway overrides this with its own PORT env var)
ENV PORT=8000

# Run FastAPI with Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]