# Production Deployment Guide — AI-BASED-SMART-HOME-SERVICES

This document provides complete, production-ready deployment instructions for the **AI-Based Smart Home Services Platform** across containerized environments, cloud VPS hosts, and managed PaaS platforms.

---

## 🏗 Platform Architecture

```
                       [ Internet Clients / Web Browsers ]
                                       │
                      ┌────────────────┴────────────────┐
                      │    Port 80 / 443 (HTTPS / WSS)   │
                      ▼                                 ▼
         [ Nginx Web Server (Frontend) ]    [ Reverse Proxy / API Gateway ]
          - React SPA static bundle          - Proxies /api/ → Backend :8000
          - Client-side routing fallback     - Proxies /ws/  → WebSocket :8000
          - Gzip & static asset caching
                      │                                 │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                       [ FastAPI Backend Container :8000 ]
                        - REST APIs & Auth (JWT)
                        - Real-Time WebSockets (Chat & GPS)
                        - Local RAG (ChromaDB + ONNX)
                        - Automated DB Migrations & Admin Seeder
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
          [ MySQL 8.0 Database ]               [ Local Persistent Storage ]
          - User, Booking, Notification        - chroma_data/ (RAG vectors)
          - Reviews & Live Location logs       - Uploads / static assets
```

---

## 🚀 Option 1: Docker Compose Deployment (Recommended for VPS / EC2)

Deploy the entire stack with a single command on any Linux server (Ubuntu/Debian, AWS EC2, DigitalOcean Droplet, Linode, Hetzner, or GCP Compute Engine).

### 1. Prerequisites on the Host Server
Install Docker and Docker Compose v2:
```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
```

### 2. Clone the Repository
```bash
git clone https://github.com/rupadevi664/AI-BASED-SMART-HOME-SERVICES.git
cd AI-BASED-SMART-HOME-SERVICES
```

### 3. Configure Production Environment
Copy the production environment template:
```bash
cp .env.production.example .env.production
```

Edit `.env.production` with your preferred editor:
```bash
nano .env.production
```

Configure your secrets:
- **`DOMAIN`**: Your domain (e.g., `https://smarthome.yourdomain.com`).
- **`MYSQL_ROOT_PASSWORD`** & **`MYSQL_PASSWORD`**: Set strong random passwords.
- **`JWT_SECRET_KEY`**: Generate a strong secret:
  ```bash
  openssl rand -hex 32
  ```
- **`ADMIN_EMAIL`** & **`ADMIN_PASSWORD`**: Credentials for your initial administrator account.
- **`CORS_ORIGINS`**: Set to your production domain(s) (e.g., `https://smarthome.yourdomain.com`).
- **`GEMINI_API_KEY`**: (Optional) Add your Google Gemini API key for AI Copilot diagnostics.
- **`RAZORPAY_KEY_ID`** & **`RAZORPAY_KEY_SECRET`**: (Optional) Add your live/test Razorpay keys for payments.

### 4. Build and Start the Stack
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

### 5. Verify Health and Status
```bash
# Check running containers
docker compose -f docker-compose.prod.yml ps

# View real-time logs
docker compose -f docker-compose.prod.yml logs -f backend

# Test Backend Health Probe
curl -f http://localhost:8000/health

# Test Frontend Nginx Probe
curl -f http://localhost/healthz
```

---

## 🌐 Setting Up SSL/TLS (HTTPS & WSS) with Certbot

To secure your production domain with free SSL certificates from Let's Encrypt:

1. Install Certbot on the host:
   ```bash
   sudo apt-get install -y certbot python3-certbot-nginx
   ```

2. Temporarily point port 80 to Certbot to obtain your certificate:
   ```bash
   sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
   ```

3. Certificates will be saved to `/etc/letsencrypt/live/yourdomain.com/`.

4. You can mount the SSL certificates into Nginx or terminate SSL at a Cloudflare / AWS Application Load Balancer layer. When using Cloudflare, set SSL mode to **Full (Strict)**.

---

## ☁️ Option 2: Cloud PaaS Deployment (Render / Railway)

### Deploying on Render.com (Blueprint)
1. Fork or push this repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com), click **New +** → **Blueprint**.
3. Connect your GitHub repository.
4. Render will automatically detect [`render.yaml`](file:///c:/Users/rupad/Documents/AI-BASED-SMART-HOME-SERVICES/render.yaml) and configure:
   - A managed MySQL database instance.
   - The FastAPI backend web service with automatic health checks (`/health`).
   - The React frontend static web service with SPA rewrite rules.
5. Fill in any private environment variables (`GEMINI_API_KEY`, `RAZORPAY_KEY_SECRET`) in the Render dashboard and click **Apply**.

### Deploying on Railway
1. Click **New Project** → **Deploy from GitHub repo**.
2. Add a **MySQL** service from the Railway templates.
3. Link the backend service:
   - Root directory: `backend`
   - Set environment variables referencing the MySQL service (`DATABASE_URL=${{MySQL.DATABASE_URL}}`).
4. Link the frontend service:
   - Root directory: `frontend`
   - Set `VITE_API_BASE_URL` to your backend's Railway URL.
5. Deploy!

---

## 🗄️ Database Backups & Maintenance

### Creating a Database Backup
```bash
docker exec -t smarthome-prod-mysql mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" ai_home_services > backup_$(date +%F_%T).sql
```

### Restoring a Database Backup
```bash
docker exec -i smarthome-prod-mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" ai_home_services < backup.sql
```

### Purging Expired GPS History
Historical live location points can be pruned according to `LOCATION_HISTORY_RETENTION_DAYS`:
```bash
docker exec -t smarthome-prod-backend python -c "from app.core.database import SessionLocal; from app.services.location_service import purge_expired_locations; db=SessionLocal(); purged=purge_expired_locations(db); print(f'Purged {purged} location fixes'); db.close()"
```

---

## 🔒 Production Security Checklist

- [x] **Strong Secrets**: Replace all default `JWT_SECRET_KEY` and database passwords with 32+ character random strings.
- [x] **Restricted CORS**: Set `CORS_ORIGINS` to exact domains; never leave as `*` in production.
- [x] **Non-Root Containers**: Backend Dockerfile runs under an unprivileged `appuser` (UID 1000).
- [x] **Internal Database**: Port 3306 is not exposed to the public internet in `docker-compose.prod.yml`.
- [x] **Log Rotation**: Containers use `json-file` logging with size caps to prevent disk exhaustion.
- [x] **Health Checks**: Containers have automated liveness/readiness probes configured (`/health`, `/healthz`).
- [x] **WebSocket Resiliency**: Frontend handles automatic reconnects, keep-alive pings, and switches to `wss://` over HTTPS.
