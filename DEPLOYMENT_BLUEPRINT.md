# 🚀 Saga Graph Deployment Blueprint

**Version:** 1.0  
**Date:** October 26, 2025  
**Purpose:** Complete deployment architecture for Digital Ocean server

---

## 📋 Architecture Overview

### System Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                           DIGITAL OCEAN DROPLET                                    │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ 
│  │                        DOCKER COMPOSE LAYER                                     │
│  ├──────────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                              │  │
│  │  ┌─────────────────────────────────┐   ┌──────────────────────────────────┐  │  │
│  │  │  Neo4j Container                │   │  Nginx Container                 │  │  │
│  │  │  ─────────────────────          │   │  ────────────────                │  │  │
│  │  │  Image: neo4j:5                 │   │  Image: nginx:alpine             │  │  │
│  │  │  Ports: 7687 (Bolt)             │   │  Port: 80 (HTTP)                 │  │  │
│  │  │         7474 (HTTP Browser)     │   │                                  │  │  │
│  │  │  Volumes: neo4j_data            │   │  Config: nginx.conf              │  │  │
│  │  │  Auth: NEO4J_USER/PASSWORD      │   │  - API key validation            │  │  │
│  │  │  Restart: unless-stopped        │   │  - Rate limiting                 │  │  │
│  │  │                                 │   │  - Reverse proxy routing         │  │  │
│  │  └─────────────────────────────────┘   └──────────────────────────────────┘  │  │
│  │                                                                              │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                      NATIVE PROCESSES (systemd)                              │  │
│  ├──────────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                              │  │
│  │  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐  │  │
│  │  │  saga-backend        │  │  saga-frontend       │  │  saga-graph        │  │  │
│  │  │  ────────────        │  │  ──────────────      │  │  ───────────       │  │  │
│  │  │  Port: 8000          │  │  Port: 5173          │  │  Background        │  │  │
│  │  │  Tech: FastAPI       │  │  Tech: Svelte+pnpm   │  │  Workers:          │  │  │
│  │  │  Setup:              │  │  Setup:              │  │                    │  │  │
│  │  │  • Python venv       │  │  • npm install pnpm  │  │  • main.py         │  │  │
│  │  │  • pip install       │  │  • pnpm install      │  │  • main_top_       │  │  │
│  │  │  • uvicorn server    │  │  • pnpm run dev      │  │    sources.py      │  │  │
│  │  │                      │  │                      │  │                    │  │  │
│  │  │  Endpoints:          │  │  Serves:             │  │  Functions:        │  │  │
│  │  │  • /api/topics       │  │  • UI components     │  │  • Article         │  │  │
│  │  │  • /api/chat         │  │  • Static assets     │  │    ingestion       │  │  │
│  │  │  • /api/articles ⚿   │  │  • Hot reload        │  │  • Analysis        │  │  │
│  │  │  • /api/users        │  │                      │  │    generation      │  │  │
│  │  │                      │  │  Connects to:        │  │  • Daily rewrites  │  │  │
│  │  │  Contains:           │  │  • Backend API       │  │  • Top sources     │  │  │
│  │  │  • Article CRUD      │  │    (port 8000)       │  │                    │  │  │
│  │  │  • User management   │  │                      │  │  Uses:             │  │  │
│  │  │  • Strategy CRUD     │  │                      │  │  • Neo4j (Bolt)    │  │  │
│  │  │                      │  │                      │  │  • Backend API ⚿   │  │  │
│  │  │  Restart: always     │  │  Restart: always     │  │  • LLM servers     │  │  │
│  │  └──────────────────────┘  └──────────────────────┘  │                    │  │  │
│  │                                                        │  Restart: always   │  │  │
│  │                                                        └────────────────────┘  │  │
│  │                                                                                │  │
│  │  ⚿ = Requires API Key (X-API-Key header)                                     │  │
│  │                                                                                │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  Data Flow:                                                                          │
│  ──────────                                                                          │
│  1. User → Nginx (port 80) → Frontend (5173) → Backend (8000) → Neo4j (7687)         │
│  2. saga-graph workers → Backend API (8000) → Neo4j (7687)                           │
│  3. External laptop → Nginx (validates API key) → Backend (8000) → Neo4j (7687)      │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ Secure Connections
                                          │ • Neo4j: bolt://server-ip:7687 (auth)
                                          │ • API: X-API-Key header validation
                                          │
┌─────────────────────────────────────────▼─────────────────────────────────────────────┐
│                              DEVELOPER LAPTOP                                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  Environment Configuration:                                                            │
│  ─────────────────────────                                                             │
│  NEO4J_URI=bolt://server-ip:7687          # Direct Neo4j access                       │
│  NEO4J_USER=neo4j                          # Neo4j authentication                      │
│  NEO4J_PASSWORD=your-password              # Neo4j authentication                      │
│  BACKEND_URL=http://server-ip/api          # Backend API endpoint                      │
│  API_KEY_LAPTOP_1=your-laptop-key          # For article operations                    │
│                                                                                        │
│  Development Workflow:                                                                 │
│  ────────────────────                                                                  │
│  1. Pull saga-graph repo locally                                                      │
│  2. Set environment variables (above)                                                  │
│  3. Run scripts that connect to production Neo4j                                      │
│  4. Create/read articles via production API                                           │
│  5. Full access to production data for development                                    │
│                                                                                        │
│  Example Usage:                                                                        │
│  ─────────────                                                                         │
│  # Direct Neo4j query                                                                 │
│  python -c "from src.graph.neo4j_client import run_cypher; print(run_cypher(...))"   │
│                                                                                        │
│  # Create article via API                                                             │
│  curl -H "X-API-Key: your-laptop-key" \                                               │
│       -X POST http://server-ip/api/articles \                                         │
│       -d '{"title": "...", "content": "..."}'                                         │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Structure

### Four Repositories

```
saga-deployment/          # NEW: Infrastructure orchestration
├── docker-compose.yml
├── deploy.sh
├── .env
├── nginx/
│   ├── nginx.conf.template
│   └── generate-config.sh
└── systemd-templates/

saga-graph/               # Core graph logic
├── start.sh
├── main.py
├── main_top_sources.py
└── src/

saga-backend/             # NEW: Extracted from API/
├── start.sh
├── api_main_v3.py
├── articles/             # MOVED from saga-graph
└── requirements.txt

saga-frontend/            # Svelte UI
├── start.sh
└── src/
```

---

## ⚙️ Environment Configuration

### .env File (saga-deployment/)

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=argosgraph

# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
ROUTED_LLM_SERVER_1=http://gate04.cfa.handels.gu.se:8686
ROUTED_LLM_SERVER_2=http://gate04.cfa.handels.gu.se:8787

# API Security - Article Endpoint Protection
# These keys protect /api/articles endpoints (GET/PUT article operations)
# Nginx validates the X-API-Key header before allowing requests through
# Use different keys for different developers/environments for access control

# Developer laptop keys (for development work)
API_KEY_LAPTOP_1=generate-random-32-char-key-1  # Primary dev laptop
API_KEY_LAPTOP_2=generate-random-32-char-key-2  # Secondary dev laptop

# Automation keys
API_KEY_CI_SERVER=generate-random-32-char-key-3  # CI/CD pipeline access
API_KEY_MOBILE_DEV=generate-random-32-char-key-4  # Mobile app development

# Environment keys
API_KEY_STAGING=generate-random-32-char-key-5    # Staging environment

# Internal key (for saga-graph workers to call saga-backend)
API_KEY_INTERNAL=internal-worker-key-32-chars    # main.py, main_top_sources.py use this

# HOW TO USE:
# Include in request header: curl -H "X-API-Key: your-key-here" http://server/api/articles/ABC123
# Nginx checks if key matches any of the above before forwarding to backend
# Invalid/missing key = 403 Forbidden response

# Ports
BACKEND_PORT=8000
FRONTEND_PORT=5173

# Repos
REPO_GRAPH=https://github.com/your-org/saga-graph.git
REPO_BACKEND=https://github.com/your-org/saga-backend.git
REPO_FRONTEND=https://github.com/your-org/saga-frontend.git
```

---

## 🐳 Docker Setup

### docker-compose.yml

```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5
    container_name: saga-neo4j
    restart: unless-stopped
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=${NEO4J_USER}/${NEO4J_PASSWORD}
      - NEO4J_server_memory_heap_initial__size=2G
      - NEO4J_server_memory_heap_max__size=4G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  nginx:
    image: nginx:alpine
    container_name: saga-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - neo4j

volumes:
  neo4j_data:
  neo4j_logs:
```

---

## 🔧 Nginx Configuration

### nginx.conf.template

```nginx
events {
    worker_connections 1024;
}

http {
    # API Key validation
    map $http_x_api_key $api_key_valid {
        default 0;
        "${API_KEY_LAPTOP_1}" 1;
        "${API_KEY_LAPTOP_2}" 1;
        "${API_KEY_CI_SERVER}" 1;
        "${API_KEY_MOBILE_DEV}" 1;
        "${API_KEY_STAGING}" 1;
        "${API_KEY_INTERNAL}" 1;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        listen 80;

        # Frontend (public)
        location / {
            proxy_pass http://host.docker.internal:5173;
        }

        # Backend API - Public endpoints
        location /api/topics {
            limit_req zone=api_limit burst=20;
            proxy_pass http://host.docker.internal:8000;
        }

        location /api/chat {
            limit_req zone=api_limit burst=20;
            proxy_pass http://host.docker.internal:8000;
        }

        # Backend API - Protected (API key required)
        location /api/articles {
            if ($api_key_valid = 0) {
                return 403 '{"error": "Invalid API key"}';
            }
            proxy_pass http://host.docker.internal:8000;
        }

        # Neo4j Browser
        location /neo4j/ {
            proxy_pass http://neo4j:7474/;
        }
    }
}
```

---

## 🔄 Code Migration

### Move API to Backend Repo

**Files to move:**
```
saga-graph/API/              → saga-backend/
saga-graph/src/articles/     → saga-backend/articles/
```

### Create Article Endpoints

**saga-backend/articles/endpoints.py (NEW):**

```python
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Dict, Any
import os

router = APIRouter(prefix="/api/articles")

async def verify_api_key(x_api_key: str = Header(...)):
    valid_keys = [
        os.getenv("API_KEY_LAPTOP_1"),
        os.getenv("API_KEY_LAPTOP_2"),
        os.getenv("API_KEY_CI_SERVER"),
        os.getenv("API_KEY_MOBILE_DEV"),
        os.getenv("API_KEY_STAGING"),
        os.getenv("API_KEY_INTERNAL"),
    ]
    if x_api_key not in valid_keys:
        raise HTTPException(403, "Invalid API Key")
    return x_api_key

@router.get("/{article_id}")
async def get_article(
    article_id: str,
    api_key: str = Depends(verify_api_key)
):
    from articles.load_article import load_article
    article = load_article(article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return article

@router.post("")
async def create_article(
    article_data: Dict[str, Any],
    api_key: str = Depends(verify_api_key)
):
    from articles.ingest_article import ingest_article_from_dict
    try:
        article_id = ingest_article_from_dict(article_data)
        return {"article_id": article_id, "status": "created"}
    except Exception as e:
        raise HTTPException(400, str(e))
```

### Create API Client in saga-graph

**saga-graph/src/api_client.py (NEW):**

```python
import requests
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY_INTERNAL")

def get_article(article_id: str):
    response = requests.get(
        f"{BACKEND_URL}/api/articles/{article_id}",
        headers={"X-API-Key": API_KEY}
    )
    return response.json() if response.status_code == 200 else None

def create_article(article_data: dict):
    response = requests.post(
        f"{BACKEND_URL}/api/articles",
        json=article_data,
        headers={"X-API-Key": API_KEY}
    )
    return response.json()["article_id"]

def list_strategies(user_id: str):
    response = requests.get(
        f"{BACKEND_URL}/api/users/{user_id}/strategies",
        headers={"X-API-Key": API_KEY}
    )
    return response.json()
```

### Update saga-graph Imports

**Replace in custom_user_analysis/:**

```python
# OLD:
from API.user_data_manager import list_strategies, load_strategy

# NEW:
from src.api_client import list_strategies, load_strategy
```

---

## 🚀 Deployment Scripts

### deploy.sh (saga-deployment/)

```bash
#!/bin/bash
set -e

# Load .env
export $(cat .env | grep -v '^#' | xargs)

# Clone/update repos
git clone $REPO_GRAPH /opt/saga-graph || (cd /opt/saga-graph && git pull)
git clone $REPO_BACKEND /opt/saga-backend || (cd /opt/saga-backend && git pull)
git clone $REPO_FRONTEND /opt/saga-frontend || (cd /opt/saga-frontend && git pull)

# Symlink .env
ln -sf $(pwd)/.env /opt/saga-graph/.env
ln -sf $(pwd)/.env /opt/saga-backend/.env
ln -sf $(pwd)/.env /opt/saga-frontend/.env

# Generate nginx config
cd nginx && ./generate-config.sh && cd ..

# Start Docker (Neo4j + Nginx)
docker-compose up -d

# Wait for Neo4j
sleep 10

# Start services
cd /opt/saga-graph && ./start.sh
cd /opt/saga-backend && ./start.sh
cd /opt/saga-frontend && ./start.sh

echo "✓ Deployment complete!"
echo "Frontend: http://localhost"
echo "Backend: http://localhost/api"
echo "Neo4j: http://localhost/neo4j"
```

### start.sh (saga-backend/)

```bash
#!/bin/bash
set -e

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/saga-backend.service > /dev/null <<EOF
[Unit]
Description=Saga Backend API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/.venv/bin"
ExecStart=$(pwd)/.venv/bin/uvicorn api_main_v3:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable saga-backend
sudo systemctl start saga-backend

echo "✓ Backend started on port 8000"
```

---

## 💻 Development Workflow

### On Server
```bash
cd /opt/saga-deployment
./deploy.sh
```

### On Laptop (Development)
```bash
# Override .env locally
export NEO4J_URI=bolt://server-ip:7687
export BACKEND_URL=http://server-ip:8000
export API_KEY_LAPTOP_1=your-key

# Work normally
python main.py  # Connects to server Neo4j
```

---

## 🔐 Security Model

| Endpoint | Auth | Method |
|----------|------|--------|
| Frontend `/` | None | Public |
| `/api/topics` | None | Public |
| `/api/chat` | None | Public |
| `/api/articles` | API Key | X-API-Key header |
| Neo4j Bolt 7687 | Neo4j | Username/password |
| Neo4j HTTP 7474 | Neo4j | Username/password |

**API Key Usage:**
```bash
curl -H "X-API-Key: your-key" http://server/api/articles/ABC123
```

---

## 📝 Summary

**What's in Docker:** Neo4j + Nginx only  
**What's Native:** Backend, Frontend, Workers (lightweight!)  
**Security:** 5 API keys + Neo4j auth  
**Deployment:** One command: `./deploy.sh`  
**Development:** Point laptop to server Neo4j + API
