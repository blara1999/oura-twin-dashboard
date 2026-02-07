# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
# Set the working directory in the container
WORKDIR /app

# Install tzdata for timezone support
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the working directory contents into the container at /app
COPY . .

# Expose the port (for documentation, Cloud Run ignores this)
EXPOSE 8080

# CRITICAL: Bind Streamlit to the PORT env var provided by Cloud Run
CMD streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0
