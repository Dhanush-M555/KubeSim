FROM python:3.9-slim

WORKDIR /app

# Copy node manager code
COPY node_manager.py /app/
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for metrics
EXPOSE 5001

# Run node manager
CMD ["python", "node_manager.py"] 