# Railway Load Testing

This project includes a small Python load test script:

```powershell
python scripts/load_test_api.py
```

The script uses the Python standard library only. It does not need `pip install`.

## What It Tests

The script checks:

- Frontend login page can be loaded or repeatedly load tested.
- Backend login works with the demo account.
- Read-only API endpoints can be called repeatedly.
- Database-backed ORM queries remain responsive under concurrent requests.

The default demo account is:

```text
username: 111001001
password: password123
```

Default target URLs:

```text
frontend: https://frontend-production-1ced.up.railway.app/#/login
backend:  https://backend-production-fe197.up.railway.app
```

## Safe Test

Run a short smoke test first:

```powershell
python scripts/load_test_api.py --users 1 --duration 5
```

Run a moderate load test:

```powershell
python scripts/load_test_api.py --target backend --skip-frontend --users 10 --duration 60 --think-time 0.2
```

Run a heavier load test:

```powershell
python scripts/load_test_api.py --target backend --skip-frontend --users 30 --duration 120 --think-time 0.1
```

By default, backend tests use `--auth-mode shared`. The script logs in once,
then reuses that token for all virtual users. This measures the API and database
load after a user is already authenticated.

If you want to stress test the login endpoint itself, use `--auth-mode per-user`:

```powershell
python scripts/load_test_api.py `
  --target backend `
  --skip-frontend `
  --auth-mode per-user `
  --login-stagger 30 `
  --users 100 `
  --duration 600 `
  --max-p95-ms 1000 `
  --max-error-rate 0.01
```

Without `--login-stagger`, all virtual users try to log in at nearly the same
time. That is useful for a login spike test, but it can hide the API/database
performance you are trying to measure.

Run a frontend load test:

```powershell
python scripts/load_test_api.py `
  --target frontend `
  --frontend-url "https://frontend-production-1ced.up.railway.app/#/login" `
  --users 100 `
  --duration 600 `
  --max-p95-ms 1000 `
  --max-error-rate 0.01
```

`#/login` is a browser-side route. The frontend server receives the `/` request,
then the browser app switches to the login route. For this reason, the script
load tests the frontend HTML page and discovered static assets such as JS and
CSS files.

Run both frontend and backend load tests in one command:

```powershell
python scripts/load_test_api.py `
  --target both `
  --frontend-url "https://frontend-production-1ced.up.railway.app/#/login" `
  --backend-url "https://backend-production-fe197.up.railway.app" `
  --auth-mode shared `
  --users 100 `
  --duration 600 `
  --max-p95-ms 1000 `
  --max-error-rate 0.01
```

Railway free or trial resources are limited. Increase `--users` slowly and watch
Railway backend logs, MySQL metrics, response time, and failed requests.

## Custom Server URL

If Railway gives you a new domain, pass it directly:

```powershell
python scripts/load_test_api.py `
  --frontend-url "https://YOUR_FRONTEND.up.railway.app/#/login" `
  --backend-url "https://YOUR_BACKEND.up.railway.app" `
  --users 10 `
  --duration 60
```

## Result Meaning

Important fields:

- `total_requests`: total requests sent.
- `success`: successful HTTP 2xx or 3xx responses.
- `failed`: failed requests.
- `avg_ms`: average response time.
- `p95_ms`: 95% of requests were faster than this value.
- `max_ms`: slowest request.

If `failed` is greater than `0`, check the `First failures` section and Railway
logs. Common causes are backend sleeping, database connection limit, wrong
frontend/backend domain, or Railway resource exhaustion.
