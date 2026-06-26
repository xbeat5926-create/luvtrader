# Vercel deployment notes

The repository includes a Vercel multi-service configuration in `vercel.json`:

- `frontend` is rooted at `frontend/`, uses the Vite framework, and is mounted at `/`.
- `backend` is rooted at `backend/` and is mounted at `/_/backend`.

For a bundled Vercel deployment, set this frontend environment variable:

```text
VITE_API_URL=/_/backend/api
```

If the FastAPI backend is hosted separately, set `VITE_API_URL` to that public backend URL instead, for example:

```text
VITE_API_URL=https://api.luvtrader.com/api
```

If you deploy only the frontend as its own Vercel project, set the Vercel project root directory to `frontend/` and point `VITE_API_URL` at the separately hosted backend.
