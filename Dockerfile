# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Ensure the data directory is writable
RUN mkdir -p /app/data && chown -R nobody:nogroup /app/data && chmod -R 755 /app/data

# Run the bot as a non-root user
USER nobody

# Command to run the bot
CMD ["python", "bot.py"]
