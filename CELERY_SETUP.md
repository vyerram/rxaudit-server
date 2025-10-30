# Celery Setup Guide for RxAudit

## Overview
This guide walks you through setting up Celery for asynchronous file processing in RxAudit. This allows multiple users to upload files concurrently without blocking each other.

## Prerequisites

### 1. Install Redis (Message Broker)

**macOS:**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**Verify Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

### 2. Install Python Dependencies

```bash
cd /Users/test/Downloads/wb/rx/rxaudit-server
pip install -r requirements.txt
```

### 3. Update Environment Variables

Add to your `.env` file:
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
```

### 4. Run Database Migrations

```bash
python manage.py migrate
```

This creates the necessary tables for `django-celery-results` to store task results.

## Running the System

You now need **3 terminal windows** running simultaneously:

### Terminal 1: Django Development Server
```bash
cd /Users/test/Downloads/wb/rx/rxaudit-server
python manage.py runserver
```

### Terminal 2: Celery Worker
```bash
cd /Users/test/Downloads/wb/rx/rxaudit-server
celery -A core worker --loglevel=info
```

### Terminal 3: Redis Server (if not running as service)
```bash
redis-server
```

## Testing the Setup

1. Upload a file through your application
2. Check the Celery worker terminal - you should see task execution logs
3. Use the new task status endpoint: `GET /api/processloghdr/{id}/task_status/`

## Production Deployment

### Using Supervisor (Recommended)

Create `/etc/supervisor/conf.d/rxaudit-celery.conf`:

```ini
[program:rxaudit-celery]
command=/path/to/venv/bin/celery -A core worker --loglevel=info --concurrency=4
directory=/path/to/rxaudit-server
user=your-user
autostart=true
autorestart=true
stderr_logfile=/var/log/celery/worker.err.log
stdout_logfile=/var/log/celery/worker.out.log
environment=DJANGO_SETTINGS_MODULE="settings"
```

Then:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start rxaudit-celery
```

### Using systemd

Create `/etc/systemd/system/celery-rxaudit.service`:

```ini
[Unit]
Description=Celery Worker for RxAudit
After=network.target redis.service

[Service]
Type=forking
User=your-user
Group=your-group
WorkingDirectory=/path/to/rxaudit-server
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A core worker --loglevel=info --concurrency=4 --detach
ExecStop=/path/to/venv/bin/celery -A core control shutdown
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-rxaudit
sudo systemctl start celery-rxaudit
```

## Monitoring

### Check Task Status via API
```bash
curl http://localhost:8000/api/processloghdr/{process_log_id}/task_status/
```

### Monitor Celery Tasks
```bash
celery -A core inspect active
celery -A core inspect stats
```

### Redis CLI
```bash
redis-cli monitor  # Watch real-time Redis commands
```

## Troubleshooting

### Issue: Tasks not executing
**Solution:** Check if Celery worker is running and connected to Redis
```bash
celery -A core inspect ping
```

### Issue: Redis connection refused
**Solution:** Ensure Redis is running
```bash
redis-cli ping
```

### Issue: Tasks failing with "Pharmacy matching query does not exist"
**Solution:** Check that pharmacy_id is being passed correctly in the task

### Issue: Old ThreadPoolExecutor still being used
**Solution:** Restart Django server after code changes

## Performance Tuning

### Adjust Worker Concurrency
```bash
# Increase workers for better parallelism (default: number of CPU cores)
celery -A core worker --concurrency=8
```

### Configure Task Time Limits
In `settings.py`:
```python
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes (warning)
```

### Monitor Queue Length
```bash
redis-cli LLEN celery
```

## Changes Summary

### Files Modified:
1. `requirements.txt` - Added Celery, Redis, django-celery-results
2. `settings.py` - Added Celery configuration
3. `core/celery.py` - Created Celery app instance
4. `core/__init__.py` - Import Celery app on startup
5. `audit/tasks.py` - Created async task for file processing
6. `audit/views.py` - Updated to use Celery instead of ThreadPoolExecutor
7. Added task status endpoint: `/api/processloghdr/{id}/task_status/`

### Architecture Changes:
- **Before:** Synchronous processing with ThreadPoolExecutor (blocked concurrent uploads)
- **After:** Asynchronous processing with Celery (supports multiple concurrent uploads)
- **Benefit:** Multiple users can upload simultaneously without performance degradation
