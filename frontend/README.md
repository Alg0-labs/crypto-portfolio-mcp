# CoinLens MCP — Frontend

The static landing page for CoinLens MCP. Deployed to **Vercel** (instant load,
no cold start). The MCP **backend** runs separately on **Render**.

```
Visitor → Vercel (this static page)        → instant, always on
AI client → Render backend (/mcp, /health) → wakes on first call
```

## One-time setup

1. Open `index.html` and set `BACKEND_ORIGIN` (top of the `<script>`) to your
   Render service URL, e.g. `https://coinmarketcap-mcp.onrender.com`.

## Deploy to Vercel

**Option A — dashboard (easiest)**
1. Push this repo to GitHub.
2. vercel.com → **Add New ▸ Project** → import the repo.
3. Set **Root Directory** to `frontend`. Framework preset: **Other**.
   Build command: *(none)*. Output directory: `.`
4. **Deploy.** You get a `*.vercel.app` URL immediately.

**Option B — CLI**
```bash
npm i -g vercel
cd frontend
vercel        # preview
vercel --prod # production
```

## Custom domain (optional, later)

Not used for now — the project runs on the default Vercel URL
(`*.vercel.app`) for the frontend and the Render URL for the backend. If you
add a custom domain later, do it in the Vercel project under
**Settings ▸ Domains**; Vercel shows the exact DNS records to set.

## Keep the backend warm (optional)

Render free tier sleeps after ~15 min idle. To avoid a cold start on the first
MCP call, ping the backend health endpoint every ~10 min with a free service
(UptimeRobot, cron-job.org): `GET https://<your-render-app>.onrender.com/health`.
