# Use an official Python runtime as a parent image
# This image is compatible with Raspberry Pi (ARM architecture)
FROM python:3.12-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
# This assumes the application code will be in a 'src' directory
 

# Define the command to run the application's entry point
CMD ["python", "main.py"]
