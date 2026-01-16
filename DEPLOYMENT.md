# Production Deployment Guide

## Prerequisites

- Docker 24+ and Docker Compose 2.20+
- AWS CLI configured (for cloud deployment)
- SSL certificates (Let's Encrypt or purchased)
- Domain name configured with DNS

## Initial Setup

### 1. Prepare Environment

```bash
# Clone repository
git clone https://github.com/NickAiNYC/Regula.git
cd Regula

# Create production environment file
cp .env.prod.example .env.prod

# Generate secrets
openssl rand -hex 32  # For SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # For ENCRYPTION_KEY

# Edit .env.prod with your actual values
nano .env.prod
```

### 2. SSL Certificates

#### Option A: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get install certbot

# Obtain certificates
sudo certbot certonly --standalone -d api.regula.health

# Copy certificates
sudo cp /etc/letsencrypt/live/api.regula.health/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/api.regula.health/privkey.pem nginx/ssl/
```

#### Option B: Self-signed (Development Only)

```bash
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem
```

### 3. Database Initialization

```bash
# Start PostgreSQL and Redis only
docker-compose -f docker-compose.prod.yml up -d postgres redis

# Wait for PostgreSQL to be ready
docker-compose -f docker-compose.prod.yml exec postgres pg_isready

# Run database migrations
docker-compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Seed rate database
docker-compose -f docker-compose.prod.yml run --rm backend python -m scripts.seed_rates
```

### 4. Start All Services

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d --build

# Check service health
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 5. Verify Deployment

```bash
# Test backend API
curl https://api.regula.health/health

# Test frontend
curl https://regula.health

# Check Prometheus metrics
curl https://api.regula.health/metrics

# Access Grafana
open http://localhost:3000  # Default: admin / <GRAFANA_PASSWORD>

# Access Celery Flower
open http://localhost:5555  # Default: <FLOWER_USER> / <FLOWER_PASSWORD>
```

## AWS ECS Deployment

### 1. Create ECS Cluster

```bash
# Create cluster
aws ecs create-cluster --cluster-name regula-production

# Create task definitions
aws ecs register-task-definition --cli-input-json file://aws/task-definition-backend.json
aws ecs register-task-definition --cli-input-json file://aws/task-definition-worker.json
```

### 2. Create Services

```bash
# Create backend service
aws ecs create-service \
  --cluster regula-production \
  --service-name regula-backend \
  --task-definition regula-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"

# Create worker service
aws ecs create-service \
  --cluster regula-production \
  --service-name regula-worker \
  --task-definition regula-worker \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}"
```

### 3. Configure Load Balancer

```bash
# Create Application Load Balancer
aws elbv2 create-load-balancer \
  --name regula-alb \
  --subnets subnet-xxx subnet-yyy \
  --security-groups sg-xxx \
  --scheme internet-facing

# Create target group
aws elbv2 create-target-group \
  --name regula-backend-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --health-check-path /health
```

## Database Backups

### Automated Backups (Built-in)

Backups run daily at 2 AM UTC via the backup container:
- 30 daily backups
- 8 weekly backups
- 12 monthly backups

### Manual Backup

```bash
# Create backup
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U regula_prod regula_prod > backup-$(date +%Y%m%d).sql

# Upload to S3
aws s3 cp backup-$(date +%Y%m%d).sql s3://regula-backups/manual/
```

### Restore from Backup

```bash
# Download backup
aws s3 cp s3://regula-backups/manual/backup-20250116.sql .

# Restore
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U regula_prod regula_prod < backup-20250116.sql
```

## Monitoring

### Prometheus Metrics

Available at: http://localhost:9090

Key metrics:
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `celery_tasks_total` - Celery task counts
- `postgres_up` - PostgreSQL availability
- `redis_up` - Redis availability

### Grafana Dashboards

Available at: http://localhost:3000

Pre-configured dashboards:
1. **Application Overview** - Request rates, error rates, latencies
2. **Database Performance** - Query times, connections, cache hit rates
3. **Celery Workers** - Task throughput, queue lengths, worker health
4. **Infrastructure** - CPU, memory, disk, network usage

### Logs

```bash
# View all logs
docker-compose -f docker-compose.prod.yml logs -f

# View specific service
docker-compose -f docker-compose.prod.yml logs -f backend

# Export logs
docker-compose -f docker-compose.prod.yml logs --no-color > logs-$(date +%Y%m%d).txt
```

## Security Checklist

- [ ] Strong passwords for all services (30+ characters)
- [ ] SSL/TLS certificates configured and valid
- [ ] Firewall rules limiting access to necessary ports only
- [ ] Database accessible only from application network
- [ ] Redis password-protected
- [ ] Environment variables not committed to git
- [ ] Regular security updates applied
- [ ] Backup encryption enabled
- [ ] Audit logging enabled
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] CSP headers set

## Maintenance

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build --no-deps backend frontend

# Run migrations if needed
docker-compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

### Scale Services

```bash
# Scale backend replicas
docker-compose -f docker-compose.prod.yml up -d --scale backend=3

# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=4
```

### Database Maintenance

```bash
# Vacuum database
docker-compose -f docker-compose.prod.yml exec postgres psql -U regula_prod -d regula_prod -c "VACUUM ANALYZE;"

# Reindex
docker-compose -f docker-compose.prod.yml exec postgres psql -U regula_prod -d regula_prod -c "REINDEX DATABASE regula_prod;"

# Check TimescaleDB compression
docker-compose -f docker-compose.prod.yml exec postgres psql -U regula_prod -d regula_prod -c "SELECT * FROM timescaledb_information.compressed_chunk_stats;"
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs backend

# Check container status
docker-compose -f docker-compose.prod.yml ps

# Restart service
docker-compose -f docker-compose.prod.yml restart backend
```

### Database Connection Issues

```bash
# Test connection
docker-compose -f docker-compose.prod.yml exec postgres psql -U regula_prod -d regula_prod -c "SELECT 1;"

# Check connections
docker-compose -f docker-compose.prod.yml exec postgres psql -U regula_prod -d regula_prod -c "SELECT * FROM pg_stat_activity;"
```

### High Memory Usage

```bash
# Check resource usage
docker stats

# Adjust resource limits in docker-compose.prod.yml
# Restart services
docker-compose -f docker-compose.prod.yml restart
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/NickAiNYC/Regula/issues
- Documentation: https://docs.regula.health
- Email: support@regula.health
