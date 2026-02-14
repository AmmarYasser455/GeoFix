FROM python:3.10-slim

# Install system dependencies (GDAL is required for Geopandas/Fiona)
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Fly.io uses 8080 by default, but we can config it)
EXPOSE 8000

# Command to run the application
CMD ["python", "-m", "uvicorn", "geofix.web.server:app", "--host", "0.0.0.0", "--port", "8000"]
