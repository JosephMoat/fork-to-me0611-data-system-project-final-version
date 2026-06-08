# Docker Deployment Guide

This project is deployed as three containers:

- `frontend`: Nginx serving the React build and proxying `/api/*` to the backend.
- `backend`: FastAPI application.
- `mysql`: MySQL 8.4 database with persistent Docker volume storage.

## 1. Server prerequisites

Install Docker Engine and Docker Compose plugin on the server.

Check installation:

```bash
docker --version
docker compose version
```

## 2. Configure environment variables

Copy the sample environment file:

```bash
cp .env.example .env
```

Edit `.env` and replace all placeholder secrets:

```env
MYSQL_ROOT_PASSWORD=use-a-strong-root-password
MYSQL_PASSWORD=use-a-strong-app-password
SECRET_KEY=use-a-long-random-secret
```

Keep this setting for normal production startup:

```env
RUN_SEED=false
```

`seed.py` deletes existing rows before inserting demo data. Only enable it for initial demo data setup.

## 3. Build and start

```bash
docker compose up -d --build
```

Open:

```text
http://SERVER_IP/
```

The frontend calls the backend through:

```text
/api
```

Nginx forwards those requests to the backend container internally.

## 4. Initialize demo data

For a demo database, run this once after the services are up:

```bash
docker compose run --rm -e RUN_SEED=true backend python seed.py
docker compose restart backend
```

Demo accounts created by the seed script:

```text
111001001 / password123
111001002 / password123
111001003 / password123
111001004 / password123
```

## 5. Useful operations

View logs:

```bash
docker compose logs -f
docker compose logs -f backend
```

Restart services:

```bash
docker compose restart
```

Stop services without deleting data:

```bash
docker compose down
```

Stop and delete database data:

```bash
docker compose down -v
```

## 6. Updating the deployment

After pulling or copying new code to the server:

```bash
docker compose up -d --build
```

## 7. HTTPS and domain setup

For a public server, put a reverse proxy such as Nginx Proxy Manager, Caddy, Traefik, or host-level Nginx in front of this compose stack.

Forward external HTTPS traffic to:

```text
127.0.0.1:${FRONTEND_PORT}
```

Keep the backend and MySQL ports private. The browser should only need access to the frontend.
