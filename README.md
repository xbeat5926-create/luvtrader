# LUVTrader MVP

LUVTrader is a full-stack operations platform for a Southwest Airlines flight attendant board-clearing service at `clients.luvtrader.com`. It replaces a manual Google Sheet workflow with role-based dashboards for admins, operations users, and clients.

## Stack

- Frontend: React + Vite
- Backend: FastAPI
- Database: MongoDB via Motor
- Auth: email/password with hashed passwords and JWT bearer tokens
- Roles: `admin`, `operations`, `client`

## Run locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000/api npm run dev
```

Seed demo data after MongoDB is running:

```bash
curl -X POST http://localhost:8000/api/seed
```

Demo users:

- Admin: `admin@luvtrader.com` / `password123`
- Operations: `ops@luvtrader.com` / `password123`
- Client: `client@example.com` / `password123`

## How the app works

Admins can manage all clients, client statuses, monthly estimates, paid amounts, internal notes, flags, settings, templates, TAP offers, financials, trips, sales, and messages. Operations users see active operational boards by default and can mark trips sold. Client users can only access their own board, balance, payment instructions, and messages.

Financial formula:

```text
balance = monthly estimate - amount paid - sold total
```

Positive balance means the client owes money. Negative balance is shown as credit/refund owed.

## Data structure

MongoDB collections:

- `users`: id, name, email, password hash, role, linked client id
- `clients`: employee number, base, CWA/legal names, contact/payment details, rotation group, monthly estimate, amount paid, sold total, balance, credit/refund, RT month, subscription type, status, notes, flags, timestamps
- `trips`: client id, trip date/type/status, sale amount, date sold, notes
- `sale_log`: client id, trip id, date sold, sale amount, running total
- `messages`: client id, type, subject, body, draft/preview/sent status, sent date, created date, triggered by, preview flag
- `settings`: payment instructions, email templates, instant-send toggles, TAP settings, global business settings

## Email preview/send mode

The backend has an email abstraction point in `render_message`. In MVP development mode, messages are logged as `previewed` records and are not actually sent. Configure `EMAIL_MODE=preview` for safe operation. Set `EMAIL_MODE=send` later and add SMTP or SendGrid values when a real provider is implemented.

Supported template triggers:

1. Monthly estimate changed
2. Last active trip sold for a client
3. RT bidding reminder template support
4. TAP retainer offer from one-button send or status changed to TAP
5. Refund/credit choice when a negative balance is calculated after a sale

## Required environment variables

See `backend/.env.example`.

- `MONGO_URL`
- `DATABASE_NAME`
- `JWT_SECRET`
- `EMAIL_MODE` (`preview` or `send`)
- Future delivery settings: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SENDGRID_API_KEY`
- Frontend: `VITE_API_URL`

## Deploy handoff

1. Provision MongoDB Atlas or a managed Mongo-compatible database.
2. Deploy FastAPI with `uvicorn main:app --host 0.0.0.0 --port $PORT` behind HTTPS.
3. Deploy the Vite build (`npm run build`) to static hosting.
4. Set `VITE_API_URL` for your deployment target; see the Vercel deployment notes below for bundled-service routing.
5. Set a strong `JWT_SECRET` and keep `EMAIL_MODE=preview` until email delivery is tested.
6. Run `/api/seed` only in staging/demo environments, not production.


### Vercel deployment

This repository contains multiple deployable services, so the root `vercel.json` uses Vercel's `experimentalServices` configuration. The Vite React frontend is served from `frontend/` at `/`, and the FastAPI backend is served from `backend/` at `/_/backend`.

For the bundled Vercel deployment, set `VITE_API_URL=/_/backend/api` so the frontend calls the backend service mounted by `vercel.json`. If the FastAPI backend is hosted separately, set `VITE_API_URL` to that public backend URL instead, for example `https://api.luvtrader.com/api`.

If you ever deploy only the frontend as its own Vercel project, set that Vercel project's root directory to `frontend/` and still configure `VITE_API_URL` to point at the separately hosted FastAPI backend.

## DNS for clients.luvtrader.com

- Create a DNS `CNAME` record for `clients` pointing to the frontend host, or an `A`/`AAAA` record if your hosting provider requires it.
- Configure the frontend host to accept `clients.luvtrader.com` as a custom domain.
- Enable HTTPS before inviting clients.
- Point API traffic to a separate backend domain or configure a reverse proxy from `/api` to FastAPI.

## Email Migration Line Item

Do **not** build Google Workspace migration inside this app. Handle it as an admin checklist:

- Set up Google Workspace for the owner email.
- Update MX records in domain DNS.
- Confirm routing before touching the old server.
- Avoid downtime by lowering TTL and testing delivery first.
- Business owner pays Google Workspace directly.
