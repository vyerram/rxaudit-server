# Docker Deployment Guide with Celery

## Overview
This guide covers deploying RxAudit with Docker, including the new Celery asynchronous processing system.

## Architecture

The Docker Compose setup includes 3 services:

1. **redis** - Message broker for Celery tasks
2. **web** - Django application (Gunicorn)
3. **celery** - Background worker for async file processing

## Quick Start

### 1. Build and Start All Services

```bash
cd /Users/test/Downloads/wb/rx/rxaudit-server
docker-compose up -d --build
```

This will start:
- Redis on port 6379
- Django web server on port 8000
- Celery worker (background)

### 2. Check Service Status

```bash
docker-compose ps
```

You should see 3 running containers:
- `rxaudit-redis`
- `rxwftest-dev-ec2-backend-ecr` (web)
- `rxaudit-celery-worker`

### 3. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f celery
docker-compose logs -f web
docker-compose logs -f redis
```

### 4. Stop Services

```bash
docker-compose down
```

## Configuration Changes Summary

### 1. `.env` File
Added:
```bash
CELERY_BROKER_URL=redis://redis:6379/0
```

**Note:** In Docker, we use `redis://redis:6379/0` (service name), not `redis://localhost:6379/0`

### 2. `docker-compose.yml`
Added:
- **redis service** - Redis 7 Alpine image with persistent volume
- **celery service** - Celery worker with 4 concurrent workers
- **redis_data volume** - Persistent Redis data storage
- **depends_on** - Ensures services start in correct order

### 3. `requirements_linux.txt`
Added:
```
celery==5.3.4
redis==5.0.1
django-celery-results==2.5.1
```

### 4. `Dockerfile`
No changes needed - already installs from `requirements_linux.txt`

## Production Deployment

### AWS ECS/EC2 Deployment

#### 1. Build and Push Docker Image

```bash
# Build image
docker build -t rxwftest-dev-ec2-backend-ecr:latest .

# Tag for ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws/i5b2u7r3
docker tag rxwftest-dev-ec2-backend-ecr:latest public.ecr.aws/i5b2u7r3/rxwftest-dev-ec2-backend-ecr:latest

# Push to ECR
docker push public.ecr.aws/i5b2u7r3/rxwftest-dev-ec2-backend-ecr:latest
```

#### 2. Deploy with Docker Compose on EC2

SSH into your EC2 instance:

```bash
ssh -i your-key.pem ec2-user@your-ec2-instance

# Clone/update repo
cd /path/to/rxaudit-server
git pull

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f
```

#### 3. Using AWS ECS (Fargate)

Create 3 ECS Task Definitions:
1. **Web Task** - Django + Gunicorn
2. **Celery Worker Task** - Celery worker
3. **Redis Task** - Or use AWS ElastiCache Redis

**Recommended:** Use AWS ElastiCache for Redis in production instead of containerized Redis.

Update `.env` to use ElastiCache endpoint:
```bash
CELERY_BROKER_URL=redis://your-elasticache-endpoint.cache.amazonaws.com:6379/0
```

## Scaling

### Scale Celery Workers

```bash
# Scale to 3 worker containers
docker-compose up -d --scale celery=3

# Or edit docker-compose.yml and add:
# deploy:
#   replicas: 3
```

### Scale Web Servers (Behind Load Balancer)

```bash
docker-compose up -d --scale web=3
```

**Note:** You'll need a load balancer (Nginx, ALB, etc.) to distribute traffic.

## Monitoring

### Check Redis Connection

```bash
docker exec -it rxaudit-redis redis-cli ping
# Should return: PONG
```

### Monitor Celery Tasks

```bash
# Active tasks
docker exec -it rxaudit-celery-worker celery -A core inspect active

# Worker stats
docker exec -it rxaudit-celery-worker celery -A core inspect stats

# Registered tasks
docker exec -it rxaudit-celery-worker celery -A core inspect registered
```

### Check Redis Queue Length

```bash
docker exec -it rxaudit-redis redis-cli LLEN celery
```

### Access Container Shell

```bash
# Django container
docker exec -it rxwftest-dev-ec2-backend-ecr bash

# Celery container
docker exec -it rxaudit-celery-worker bash

# Redis container
docker exec -it rxaudit-redis sh
```

## Troubleshooting

### Issue: Celery worker can't connect to Redis
**Check:**
```bash
docker-compose logs redis
docker-compose logs celery
```

**Solution:** Ensure `CELERY_BROKER_URL=redis://redis:6379/0` in `.env` (use service name `redis`, not `localhost`)

### Issue: Tasks not processing
**Check:**
```bash
docker-compose logs celery | grep ERROR
docker exec -it rxaudit-celery-worker celery -A core status
```

**Solution:** Restart Celery worker:
```bash
docker-compose restart celery
```

### Issue: Redis data lost after restart
**Check:** Ensure volume is defined in docker-compose.yml
```yaml
volumes:
  redis_data:
```

**Solution:** Redis data persists in `redis_data` volume. To clear:
```bash
docker-compose down -v  # WARNING: Deletes all volumes
```

### Issue: Out of memory
**Solution:** Limit container resources in docker-compose.yml:
```yaml
celery:
  deploy:
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 1G
```

### Issue: Web container fails to start
**Check logs:**
```bash
docker-compose logs web
```

**Common causes:**
- Database connection issues
- Missing migrations
- Environment variables not set

**Solution:**
```bash
# Run migrations manually
docker exec -it rxwftest-dev-ec2-backend-ecr python manage.py migrate

# Check database connection
docker exec -it rxwftest-dev-ec2-backend-ecr python manage.py dbshell
```

## Environment-Specific Configurations

### Development (.env.dev)
```bash
CELERY_BROKER_URL=redis://redis:6379/0
DEBUG=True
```

### Production (.env.prod)
```bash
CELERY_BROKER_URL=redis://your-elasticache.cache.amazonaws.com:6379/0
DEBUG=False
```

Use different env files:
```bash
docker-compose --env-file .env.prod up -d
```

## Health Checks

Add health checks to docker-compose.yml:

```yaml
web:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
    interval: 30s
    timeout: 10s
    retries: 3

celery:
  healthcheck:
    test: ["CMD", "celery", "-A", "core", "inspect", "ping"]
    interval: 30s
    timeout: 10s
    retries: 3

redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

## Backup and Restore

### Backup Redis Data
```bash
docker exec rxaudit-redis redis-cli BGSAVE
docker cp rxaudit-redis:/data/dump.rdb ./backup/
```

### Restore Redis Data
```bash
docker cp ./backup/dump.rdb rxaudit-redis:/data/
docker-compose restart redis
```

## Performance Tips

1. **Use ElastiCache in Production** - More reliable than containerized Redis
2. **Scale Celery Workers** - Add workers based on queue length
3. **Monitor Memory** - Celery workers can consume memory over time
4. **Set Task Time Limits** - Already configured (30 min timeout)
5. **Use Connection Pooling** - Django already configured with CONN_MAX_AGE

## Next Steps After Deployment

1. Upload test files via API/UI
2. Monitor Celery logs: `docker-compose logs -f celery`
3. Check task status: `GET /api/processloghdr/{id}/task_status/`
4. Set up CloudWatch logs for production monitoring
5. Configure auto-scaling for Celery workers based on queue length
