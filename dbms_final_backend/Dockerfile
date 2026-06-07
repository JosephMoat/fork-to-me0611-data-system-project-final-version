FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure start.sh is executable
RUN chmod +x start.sh

# Expose port
EXPOSE 8000

# Run start script
CMD ["./start.sh"]
