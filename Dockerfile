# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the project files to the container
COPY . /app

# Rename the example config file to the actual config file
RUN cp /app/config.yml.example /app/config.yml

# Install Poetry
RUN pip install poetry

# Install the project dependencies with Poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev

# Command to run the bot
CMD ["poetry", "run", "python3", "main.py"]
