# ==============================================================================
# Production Multi-Stage Dockerfile for Frontend (React + Vite + Nginx)
# Stage 1: Build static distribution
# Stage 2: High-performance Nginx web server
# ==============================================================================

# --- Stage 1: Build ---
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests and install dependencies
COPY frontend/package*.json ./
RUN npm ci --silent

# Build arguments for API and WebSocket URLs (defaults to same-origin / fallback)
ARG VITE_API_BASE_URL=""
ARG VITE_WS_BASE_URL=""

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_BASE_URL=${VITE_WS_BASE_URL}

# Copy frontend source code
COPY frontend/ ./

# Build production bundle
RUN npm run build

# --- Stage 2: Production Nginx Server ---
FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy optimized Nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
