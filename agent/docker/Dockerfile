# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Make port 8080 available to the world outside this container
# App Runner will map its public port to this one
EXPOSE 8080

# Define environment variables (App Runner can override these)
ENV FLASK_APP=app.py

# Set defaults or rely on App Runner env vars
ENV BEDROCK_AGENT_ID="YOUR_AGENT_ID"

# Set defaults or rely on App Runner env vars
ENV BEDROCK_AGENT_ALIAS_ID="YOUR_AGENT_ALIAS_ID"

ENV AWS_REGION="us-east-1"

# Run app.py when the container launches using Gunicorn
# Listen on all interfaces (0.0.0.0) on the exposed port
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]