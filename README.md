# LPD&M Cleaning Solutions

**Live site:** [lpdmcleaning.co.uk](https://lpdmcleaning.co.uk)

Professional cleaning services website for LPD&M Cleaning Solutions Ltd, based in Enfield, North London. The platform lets prospective clients browse services and submit quote requests, which are captured in a cloud database and surfaced in a private admin dashboard for the business owner to action.

---

## Architecture

The application is split into two independent layers — a static frontend and a serverless backend — so neither layer needs the other to be running in order to develop or test it.

```
Browser
  │
  ├─── Static Assets (HTML / CSS / JS / Images)
  │         │
  │    CloudFront CDN  (HTTPS, global edge caching)
  │         │
  │      S3 Bucket  (lpdmcleaning.co.uk)
  │
  └─── Quote Form POST / Admin API calls
            │
       API Gateway  (HTTP API, eu-west-2)
            │
        AWS Lambda  (Python 3.12, 128 MB)
            │
         FastAPI app  (Mangum ASGI adapter)
            │
         DynamoDB  (table: lpdm-quotes, PAY_PER_REQUEST)

Domain & SSL
  Route 53  →  lpdmcleaning.co.uk
  ACM Certificate  (us-east-1, required for CloudFront)
```

---

## Tech Stack

| Layer | Technology | Reason chosen |
|---|---|---|
| Frontend | Plain HTML5 / CSS3 / Vanilla JS | No build step needed; S3 serves files directly |
| Styling | Custom CSS (no framework) | Full control; no unused utility classes to strip |
| Icons | Font Awesome 6 CDN | Avoids hosting icon assets |
| Backend | Python 3.12 + FastAPI | Fast, async, automatic OpenAPI docs |
| ASGI adapter | Mangum | Bridges FastAPI to Lambda's event/context model |
| Database | AWS DynamoDB (PAY_PER_REQUEST) | Serverless, scales to zero when idle, no connection pool needed |
| Hosting | AWS S3 + CloudFront | Cheap, globally fast, no server to maintain |
| Domain | AWS Route 53 + ACM SSL | Native integration with CloudFront |
| Version control | Git / GitHub | |

---

## Project Structure

```
lpdmcleaning/
├── index.html           # Homepage with hero carousel and services overview
├── services.html        # Full services catalogue with pricing
├── about.html           # Team profiles and company story
├── contact.html         # Contact form and business info
├── quote.html           # Dedicated quote request form
├── rental.html          # Rental Services coming-soon page
├── Dashboard.html       # Private admin dashboard (password-protected, client-side)
├── privacy.html         # Privacy Policy
├── terms.html           # Terms & Conditions
│
├── styles.css           # Global stylesheet (one file, no preprocessor)
├── script.js            # All frontend JS: form handling, nav, carousel, animations
│
├── images/              # All site images — logos, team photos, service photos
│   ├── logo_new.png
│   ├── REG.jpeg / mindy.jpg / michael.jpg   # Team photos
│   └── ETC.jpg / DCS.jpg / PCS.jpg / ...   # Service category photos
│
├── robots.txt           # Tells search engines what to index
├── sitemap.xml          # Helps Google discover all pages faster
│
└── backend/
    ├── main_lambda.py   # FastAPI app — the file deployed to Lambda
    ├── main.py          # FastAPI app for local development (uvicorn)
    └── requirements.txt # Python dependencies
```

---

## Running Locally

### Frontend

No build step is required. Serve the root folder with any static file server:

```bash
# Python (built-in — no install needed)
python -m http.server 5001 --directory .

# Then open: http://localhost:5001
```

By default the quote form will POST to the live AWS Lambda endpoint. To point it at a local backend instead, add this snippet **before** `script.js` loads in `index.html`:

```html
<script>
  window.LPDM_CONFIG = {
    API_QUOTE_ENDPOINT: 'http://localhost:8000/v1/quote'
  };
</script>
```

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the dev server (hot-reload enabled)
uvicorn main:app --reload --port 8000

# API docs available at: http://localhost:8000/docs
```

> The local backend uses the same DynamoDB table as production. To avoid touching live data during development, create a second table (e.g. `lpdm-quotes-dev`) and update `TABLE_NAME` in `main.py`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/quote` | Submit a new quote request (public) |
| `GET` | `/v1/admin/quotes` | List all quotes, newest first (admin) |
| `GET` | `/v1/admin/quotes/{id}` | Fetch a single quote by UUID (admin) |
| `POST` | `/v1/admin/quotes/{id}/respond` | Mark a quote as Responded (admin) |
| `GET` | `/health` | Health check — returns timestamp |

Full interactive docs when running locally: `http://localhost:8000/docs`

---

## Deployment

### Frontend → S3 + CloudFront

```bash
# Sync all static files to S3 (excludes dev/build artefacts)
python -m awscli s3 sync . s3://lpdmcleaning.co.uk/ \
  --exclude ".git/*" --exclude ".gitignore" --exclude ".claude/*" \
  --exclude "backend/*" --exclude "files/*" --exclude "*.zip" \
  --exclude "*.db" --exclude "__pycache__/*" --exclude ".venv/*" \
  --exclude "*.code-workspace" --exclude "README.md"

# Bust the CDN cache so visitors immediately see the new version
python -m awscli cloudfront create-invalidation \
  --distribution-id YOUR_CLOUDFRONT_DISTRIBUTION_ID --paths "/*"
```

### Backend → AWS Lambda

```bash
cd backend

# Install dependencies into a local package folder
pip install -r requirements.txt --target ./lpdm_lambda_pkg

# Bundle the app + dependencies into a zip
cp main_lambda.py lpdm_lambda_pkg/
cd lpdm_lambda_pkg && zip -r ../lpdm_lambda.zip . && cd ..

# Upload to Lambda
python -m awscli lambda update-function-code \
  --function-name lpdm-quote-api \
  --zip-file fileb://lpdm_lambda.zip \
  --region eu-west-2
```

---

## Environment & AWS Resources

| Resource | Name / ID |
|---|---|
| S3 Bucket | `lpdmcleaning.co.uk` |
| CloudFront Distribution | `YOUR_CLOUDFRONT_DISTRIBUTION_ID` |
| Lambda Function | `lpdm-quote-api` (eu-west-2) |
| API Gateway | HTTP API → `YOUR_API_GATEWAY_ID.execute-api.eu-west-2.amazonaws.com` |
| DynamoDB Table | `lpdm-quotes` (eu-west-2, PAY_PER_REQUEST) |
| Route 53 Hosted Zone | `lpdmcleaning.co.uk` |

No API keys or secrets are stored in this repository. AWS access is provided at runtime via IAM role attached to the Lambda function.

---

## Admin Dashboard

`Dashboard.html` is a client-side admin panel accessible at `/Dashboard.html`. It is protected by a SHA-256 password hash checked in the browser. The session is stored in `sessionStorage` and expires when the tab is closed.

> This is lightweight protection suitable for an internal tool. For a public-facing admin panel, replace this with server-side authentication.

---

## Social Media

- Instagram: [@lpdm_cleaning_services](https://www.instagram.com/lpdm_cleaning_services)
- TikTok: [@lpdmcleaning](https://www.tiktok.com/@lpdmcleaning)

---

## Contact

**LPD&M Cleaning Solutions Ltd**
Enfield, London
📞 +44 7495 687854
✉️ lpdmcleaning@gmail.com
🕐 Monday – Sunday, 8:00 AM – 8:00 PM

---

*Website designed and developed by [RegnabTec](https://your-portfolio-link.com)*
