# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the working directory contents into the container at /app
COPY . .

# Expose port 8080 (Cloud Run uses 8080 by default)
EXPOSE 8080

# Run the application
# Cloud Run expects the app to listen on the PORT environment variable (default 8080)
# Streamlit needs --server.port and --server.address to bind correctly
CMD streamlit run app.py --server.port 8080 --server.address 0.0.0.0
