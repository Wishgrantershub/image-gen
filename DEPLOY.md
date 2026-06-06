# Deploying ComicMe to Vercel + Railway + Neon + R2

This guide walks through deploying the ComicMe FastAPI backend to **Railway**
(Neon Postgres, Cloudflare R2 for PDF storage) and the TanStack Start frontend
to **Vercel**.

> **Pre-reqs:** a GitHub repo containing this codebase, accounts on
> Vercel, Railway, Neon, and Cloudflare, and a Razorpay account (only if
> you want to enable paid tiers in production).

The repo already has the right deploy configs checked in:
- `Procfile` and `railway.toml` at the repo root → used by Railway
- `runtime.txt` at the repo root → pins Python 3.11.9
- `frontend/vercel.json` → used by Vercel (builds TanStack Start → `.output/`)

You do **not** need to move or rename any folders. Vercel and Railway each
point to the right subdirectory in their own project settings.

---

## 0. Sanity check the local dev path still works

Before deploying, confirm the local stack still runs end-to-end:

```bash
# Terminal 1 — backend
. C:\Users\ganga\Documents\envs\image-gen\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open `http://localhost:3000` and create a comic. The startup banner in the
backend terminal should now look like:

```
2026-06-06 11:42:01 INFO     comicme | startup complete | env=development db=sqlite:///./diffrun.db r2=(none) razorpay=disabled cors_origins=1
```

If you see that, the logging and config changes are working.

---

## 1. Neon — provision the database

1. Sign in at https://console.neon.tech
2. Create a new project, pick a region close to your Railway deploy region
3. Open the **Connection Details** panel, copy the **Pooled** connection string
   (it will look like `postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require`)
4. Either:
   - **Option A (one var):** paste the entire URL into a single `DATABASE_URL`
     env var on Railway, **or**
   - **Option B (split vars, matches ourverse):** leave `DATABASE_URL` empty
     and fill in the 6 individual vars on Railway:
     ```
     DB_HOST=ep-xxx.us-east-2.aws.neon.tech
     DB_PORT=5432
     DB_USER=neondb_owner
     DB_PASSWORD=...
     DB_NAME=neondb
     DB_SSLMODE=require
     ```
   The FastAPI startup banner will show which one is active. Both work.

5. (Optional) Open the Neon SQL editor and run `SELECT 1;` to confirm you
   can reach the DB.

---

## 2. Cloudflare R2 — provision the bucket

1. Sign in at https://dash.cloudflare.com → **R2** → **Create bucket**
2. Name it `comicme-pdfs` (or anything — `R2_BUCKET_NAME` is what matters)
3. (Optional, but recommended) **Settings** → **Public access** → **Connect
   domain** or **R2.dev subdomain** → enable. Copy the public URL (looks like
   `https://pub-<account_id>.r2.dev`). This gives the browser direct download
   links instead of presigned URLs.
4. **R2** → **Manage R2 API Tokens** → **Create API token**
   - Permissions: Object Read & Write
   - Bucket scope: `comicme-pdfs`
   - Copy the **Access Key ID** and **Secret Access Key**
5. Copy your **Account ID** from the R2 overview page (used to build the
   endpoint URL: `https://<account_id>.r2.cloudflarestorage.com`)

The 4 production env vars you'll paste into Railway:
```
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=comicme-pdfs
R2_PUBLIC_URL=https://pub-<account_id>.r2.dev      # optional but recommended
R2_ENABLED=true                                    # turns the backend on
```

If you skip `R2_PUBLIC_URL`, the backend will auto-derive it from `R2_ACCOUNT_ID`
and fall back to presigned URLs. With it set, browsers get direct CDN-style
downloads.

---

## 3. Railway — deploy the backend

1. Sign in at https://railway.app
2. **New Project** → **Deploy from GitHub repo** → pick this repo
3. Railway auto-detects the `Procfile` and `railway.toml` at the repo root.
   It will:
   - Pin Python 3.11.9 via `runtime.txt`
   - Install from `requirements.txt` via Nixpacks
   - Run `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (from `railway.toml`)
4. Once the first build finishes, click the service → **Variables** and add
   everything from `.env.example` (production values). At minimum:
   ```
   ENVIRONMENT=production
   SECRET_KEY=<long random string>
   GEMINI_API_KEY=...
   CORS_ORIGINS=https://<your-frontend>.vercel.app
   DATABASE_URL=<from step 1>      # OR fill DB_HOST/DB_USER/...
   R2_ENABLED=true
   R2_ACCOUNT_ID=...
   R2_ACCESS_KEY_ID=...
   R2_SECRET_ACCESS_KEY=...
   R2_BUCKET_NAME=comicme-pdfs
   R2_PUBLIC_URL=https://pub-<account>.r2.dev
   ```
   Leave `RAZORPAY_ENABLED=false` for the initial deploy if you haven't
   wired real Razorpay keys yet. The demo-bypass flow works end-to-end in
   that mode.
5. **Settings** → **Networking** → **Generate Domain**. Copy the URL
   (e.g. `https://comicme-backend.up.railway.app`).
6. **Settings** → **Healthcheck Path**: `healthz` (already in `railway.toml`)
7. **Deploy** should trigger automatically on the first variables save. Watch
   the logs — the first line should be:
   ```
   2026-06-06 11:42:01 INFO  comicme | startup complete | env=production db=postgresql+psycopg://neondb_owner:***@ep-xxx.../neondb?sslmode=require r2=https://<account>.r2.cloudflarestorage.com bucket=comicme-pdfs razorpay=disabled cors_origins=1
   ```
   If `db` shows `sqlite:///./diffrun.db` instead of the Neon URL, your
   `DATABASE_URL` or `DB_HOST` didn't make it into the env. Check the
   Variables tab.

### Smoke test the backend

```bash
curl https://<your-railway-domain>.up.railway.app/healthz
# {"status":"ok"}

curl https://<your-railway-domain>.up.railway.app/api/comics/styles | head -c 200
# should be a JSON listing of manga / pixar / superhero styles
```

---

## 4. Vercel — deploy the frontend

1. Sign in at https://vercel.com
2. **Add New…** → **Project** → import this same GitHub repo
3. In the **Configure Project** screen:
   - **Root Directory:** click **Edit** → set to `frontend`
   - **Framework Preset:** Other (TanStack Start is auto-detected via
     `vercel.json`, but selecting Other is safest)
   - **Build Command:** `npm run build` (default)
   - **Output Directory:** `.output` (Nitro default; already in
     `frontend/vercel.json`)
4. **Environment Variables**:
   - `VITE_API_BASE` = `https://<your-railway-domain>.up.railway.app`
     (no trailing slash)
5. Click **Deploy**. First build takes 1-2 minutes (Nitro + TanStack Start).
6. Vercel assigns a domain like `comicme-frontend.vercel.app`. Open it.
7. Create a comic end-to-end. The Railway logs should now show:
   ```
   2026-06-06 11:55:02 INFO  comicme.comics | [comics.create] story=42 tier=premium session=abc12345... payment_verified=False share_token=xyz
   2026-06-06 11:55:02 INFO  comicme.comics | [comics.bg] story=42 user=100 style=manga tier=premium background task started
   2026-06-06 11:55:04 INFO  comicme.comic_service | [comic_svc] story=42 START style=manga tier=premium child="Maya"
   2026-06-06 11:55:04 INFO  comicme.comic_service | [comic_svc] story=42 step=script pct=8 msg="Writing the script..."
   2026-06-06 11:55:18 INFO  comicme.comic_service | [comic_svc] story=42 step=panel_1 pct=29 msg="Drawing panel 1 of 6..."
   ... (more panel steps)
   2026-06-06 11:56:10 INFO  comicme.comic_service | [comic_svc] story=42 PDF built at /app/output/comics/comic_42.pdf — uploading via r2 backend
   2026-06-06 11:56:11 INFO  comicme.storage    | [storage] R2 upload start story=42 key=comics/comic_42.pdf size=1340KB endpoint=https://<account>.r2.cloudflarestorage.com
   2026-06-06 11:56:12 INFO  comicme.storage    | [storage] R2 upload success story=42 key=comics/comic_42.pdf -> https://pub-<account>.r2.dev/comics/comic_42.pdf
   2026-06-06 11:56:12 INFO  comicme.comic_service | [comic_svc] story=42 DONE backend=r2 storage_key=comics/comic_42.pdf
   ```
8. On the frontend, the **My Library** page should show the new comic and
   the **Export PDF** button should download directly from R2.

---

## 5. Optional: enable Razorpay in production

Once you're ready to charge real money:

1. Log into https://dashboard.razorpay.com → **Settings** → **API Keys**
2. Switch to **Live Mode** (top right), generate a Live key pair
3. Add to Railway Variables:
   ```
   RAZORPAY_ENABLED=true
   RAZORPAY_LIVE_MODE=true
   RAZORPAY_KEY_ID=rzp_live_...
   RAZORPAY_KEY_SECRET=...
   ```
4. Restart the Railway service.
5. The frontend `/api/payment/config` endpoint will now return
   `razorpay_enabled: true` and the checkout will open a real payment
   window instead of the demo bypass.

If you only want to test the live key in test mode first, use
`RAZORPAY_LIVE_MODE=false` and the `rzp_test_...` key pair.

---

## 6. Things to know about this deploy

### Session token = browser localStorage

The "My Comics" library uses a `X-Session-Token` header that the frontend
stores in `localStorage` as `comicme_session_token`. This means:
- **Clearing browser data = losing the library** (expected for the no-account
  flow)
- **Incognito windows have a separate library** (expected)
- **Different browsers / devices don't share a library** (this is the
  intended v1 behavior)

If you later add real accounts, swap this for a JWT.

### Long-running comic generation

A 6-panel comic takes ~60-90s end-to-end. The frontend polls
`GET /api/comics/by-token/<share_token>/status` every 2.5s and updates a
progress bar. The status endpoint is also session-friendly.

If Railway kills the worker mid-generation (e.g. deploy), the job is lost.
This is the same limitation as every other "fire-and-forget background task"
service. For a more durable pipeline, add Redis + a worker process — but
that's out of scope for v1.

### R2 quirks

- The endpoint format is `https://<account_id>.r2.cloudflarestorage.com`
- R2 requires `s3={"addressing_style": "path"}` on the boto3 client
  (already set in `app/services/storage.py`) — without it, presigned URLs
  fail
- Egress from R2 is **free**, so don't worry about download traffic

### Logs and observability

Railway streams stdout to its log viewer. Every log line is prefixed with:
```
YYYY-MM-DD HH:MM:SS LEVEL  logger_name | message
```

Useful greppable tags:
- `[comics.create]` — a new comic was queued
- `[comics.bg]` — the background task picked it up
- `[comic_svc]` — every step transition in the pipeline
- `[storage]` — R2 upload start/success/failure
- `[payment.verify]` / `[payment.demo_bypass]` / `[payment.create_order]` — payment flow
- `[library.list]` / `[library.delete]` — library activity
- `[main] startup complete` — boot banner (env + db + r2 + cors summary)

To see the per-poll status traffic, set `LOG_LEVEL=DEBUG` in Railway. The
poll lines use `logger.debug(...)` and are off by default to avoid spam.

### Costs (low-traffic assumption)

- Railway: $5/mo hobby plan, includes 500h compute + 100GB egress
- Neon: free tier covers 0.5GB storage + 190 compute hours/mo
- Cloudflare R2: free tier covers 10GB storage + 10M requests/mo, no egress
- Vercel: free tier covers hobby projects, 100GB egress/mo
- Razorpay: 2% per successful transaction (no monthly fee)

Realistic monthly cost at low traffic: **$5 (just Railway)**.

---

## 7. Rollback

If a deploy breaks:
- **Railway:** Deployments tab → click any previous successful deploy →
  **Redeploy**
- **Vercel:** Deployments tab → click the last working deployment →
  **Promote to Production**

Both keep full history. The Postgres schema is additive (only `ALTER TABLE
... ADD COLUMN IF NOT EXISTS`), so a redeploy of an older code version
won't break the DB.

---

## 8. Local dev vs production — env file

Your local `.env` should look like the dev section of `.env.example`:
```
ENVIRONMENT=development
GEMINI_API_KEY=...
DATABASE_URL=sqlite:///./diffrun.db
# everything else can be blank / default
```

The Railway service uses the production values from `.env.example` (the
comments explain each var). Don't copy your local `.env` to Railway.
