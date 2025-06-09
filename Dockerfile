FROM python:3.12.4-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app \
    APP_HOME=/home/app/web \
    PORT=8000

# Create application directories
RUN mkdir -p $APP_HOME
WORKDIR $APP_HOME

# Copy application files
COPY . $APP_HOME

# Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-traditional dos2unix&& \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN dos2unix $APP_HOME/entrypoint.prod.sh    
# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements_linux.txt

# Make scripts and app directories executable
RUN chmod +x $APP_HOME/entrypoint.prod.sh
RUN chmod +x $APP_HOME

# Expose the application port
EXPOSE 8000

# Set the default command to run Gunicorn with the updated configuration
CMD ["gunicorn", "-w", "8", "core.wsgi:application", "--timeout", "300", "--bind", "0.0.0.0:8000"]
