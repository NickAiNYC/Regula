# Regula Health - Quick Start Guide

## Development Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Node.js 20+

### 1. Clone and Setup Environment

```bash
# Clone repository
git clone https://github.com/NickAiNYC/Regula.git
cd Regula

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Start Services with Docker Compose

```bash
# Start all services (database, Redis, backend, frontend)
docker-compose up -d

# View logs
docker-compose logs -f backend
```

### 3. Initialize Database

```bash
# Access backend container
docker-compose exec backend bash

# Run database initialization (create tables)
python -c "import asyncio; from app.db.session import init_db; asyncio.run(init_db())"

# Exit container
exit
```

### 4. Access Application

- **Frontend**: http://localhost:5173
- **API Documentation**: http://localhost:8000/api/v1/docs
- **Health Check**: http://localhost:8000/health

### 5. Create Test User (via API)

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecurePass123!",
    "full_name": "Admin User",
    "organization_name": "Test Behavioral Health"
  }'
```

## Local Development (without Docker)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis locally
# Update .env with local connection strings

# Run server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Testing

```bash
# Backend tests (coming soon)
cd backend
pytest tests/ -v

# Frontend tests (coming soon)
cd frontend
npm run test
```

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment guides.

## Architecture

- **Backend**: FastAPI (Python 3.12) with async SQLAlchemy
- **Frontend**: React 19 + TypeScript + Vite
- **Database**: PostgreSQL 16 with TimescaleDB
- **Cache**: Redis 7
- **Security**: JWT authentication, AES-256 PHI encryption

## Key Features Implemented

✅ User authentication (JWT + OAuth2)
✅ EDI 835 file parsing
✅ Rate engine with geographic adjustments
✅ Violation detection algorithm
✅ Real-time dashboard
✅ Multi-tenant architecture
✅ HIPAA-compliant PHI encryption

## Next Steps

- [ ] Seed rate database with NY Medicaid rates
- [ ] Add provider management
- [ ] Implement appeal tracking
- [ ] Add DFS demand letter generation
- [ ] Set up comprehensive testing
- [ ] Configure CI/CD pipeline

## Support

For issues or questions, please open a GitHub issue or contact support@regula.health
