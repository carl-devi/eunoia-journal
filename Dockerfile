# Use the official lightweight Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run the web service on container startup using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]