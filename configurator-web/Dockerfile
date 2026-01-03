FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY configurator_app.py .
COPY docker_manager.py .
COPY compose_generator.py .
COPY file_browser.py .
COPY static/ ./static/
COPY templates/ ./templates/

# Set environment variables
ENV FLASK_APP=configurator_app.py
ENV PYTHONUNBUFFERED=1
ENV WORKSPACE_PATH=/workspace
ENV CONFIG_PATH=/config
ENV HOST_MOUNT=/host

# Expose port
EXPOSE 8009

# Run the application
CMD ["python", "configurator_app.py"]
