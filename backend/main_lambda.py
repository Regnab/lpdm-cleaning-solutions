"""
LPD&M Cleaning Solutions — Quote Request API
=============================================
Runtime:   AWS Lambda (Python 3.12, eu-west-2)
Database:  DynamoDB table → lpdm-quotes
Trigger:   API Gateway HTTP API (stage: /v1)
Handler:   main_lambda.handler

What this file does:
  Receives quote requests submitted through the website contact form,
  stores them permanently in DynamoDB, and exposes a private admin
  API so the business owner can view and action them from the dashboard.

Why serverless (Lambda + DynamoDB)?
  The site receives bursts of traffic rather than a steady stream.
  Lambda scales to zero when idle (no cost) and spins up in milliseconds
  for each request — no server to maintain or pay for 24/7.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum          # bridges FastAPI (ASGI) to Lambda's event model
from pydantic import BaseModel
from typing import Optional
from botocore.exceptions import ClientError
import boto3
import uuid
from datetime import datetime, timezone


app = FastAPI(title="LPD&M Quote API", version="3.0.0")


# ── CORS ──────────────────────────────────────────────────────────────────────
# We explicitly list the domains allowed to call this API.
# Without this, browsers will block the quote form from posting to Lambda
# because the site (lpdmcleaning.co.uk) and the API are on different domains.
# localhost entries are here so developers can test locally without deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lpdmcleaning.co.uk",
        "https://www.lpdmcleaning.co.uk",
        "http://localhost:5001",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Database connection ────────────────────────────────────────────────────────
TABLE_NAME = "lpdm-quotes"

def get_table():
    # We create a fresh DynamoDB resource on each call rather than a module-level
    # singleton. Lambda may reuse the same container across requests, but keeping
    # the connection creation here avoids stale connection issues after cold starts.
    return boto3.resource("dynamodb", region_name="eu-west-2").Table(TABLE_NAME)


# ── Request model ──────────────────────────────────────────────────────────────
# Pydantic validates the incoming JSON automatically. If a required field is
# missing or the wrong type, FastAPI returns a clear 422 error before our
# code even runs — no manual validation boilerplate needed.
class QuoteRequest(BaseModel):
    name:             str
    email:            str
    phone:            str
    service:          str
    property_size:    Optional[str] = None
    message:          Optional[str] = None
    preferred_date:   Optional[str] = None
    referral_source:  Optional[str] = None
    source:           Optional[str] = None
    submitted_at:     Optional[str] = None   # client sends this but we ignore it —
                                             # the server sets the authoritative timestamp


# ── POST /v1/quote ─────────────────────────────────────────────────────────────
# Public endpoint — called by the website quote form.
# Creates a new quote record and returns the generated ID so the frontend
# can reference it in any follow-up communication.
@app.post("/v1/quote", status_code=201)
async def receive_quote(req: QuoteRequest):
    # UUID gives every quote a globally unique, unguessable identifier.
    # This prevents clients from iterating over sequential IDs to harvest data.
    quote_id = str(uuid.uuid4())

    item = {
        "id":               quote_id,
        "name":             req.name,
        "email":            req.email,
        "phone":            req.phone,
        "service":          req.service,
        "property_size":    req.property_size  or "",
        "message":          req.message        or "",
        # Always use UTC so timestamps sort correctly regardless of where
        # Lambda happens to be running or where the client is located.
        "submitted_at":     datetime.now(timezone.utc).isoformat(),
        "preferred_date":   req.preferred_date  or "",
        "referral_source":  req.referral_source or "",
        # Default status is "New" so the admin dashboard can filter
        # unread quotes at a glance without scanning the whole table.
        "status":           "New",
    }

    try:
        get_table().put_item(Item=item)
        return {"status": "success", "id": quote_id}
    except Exception as e:
        # Surface the real error in the response so CloudWatch logs capture it.
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /v1/admin/quotes ───────────────────────────────────────────────────────
# Private endpoint — called by Dashboard.html to populate the quote list.
# Returns all quotes sorted newest-first so the business owner sees the
# most recent enquiries without having to scroll.
@app.get("/v1/admin/quotes")
async def list_quotes():
    try:
        # DynamoDB Scan reads every item in the table. This is fine for a small
        # business volume. If the table grows to thousands of rows, replace with
        # a GSI (Global Secondary Index) query on submitted_at for efficiency.
        resp  = get_table().scan()
        items = resp.get("Items", [])
        items.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /v1/admin/quotes/{quote_id} ───────────────────────────────────────────
# Fetches a single quote in full detail — used when the admin clicks "View"
# on a quote in the dashboard to read the full message and contact info.
@app.get("/v1/admin/quotes/{quote_id}")
async def get_quote(quote_id: str):
    try:
        resp = get_table().get_item(Key={"id": quote_id})
        item = resp.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Quote not found.")
        return item
    except HTTPException:
        raise   # re-raise our own 404 without wrapping it in a 500
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /v1/admin/quotes/{quote_id}/respond ──────────────────────────────────
# Marks a quote as "Responded" so it moves out of the "New" inbox.
# Uses a ConditionExpression to guarantee the quote exists before updating —
# without this, DynamoDB would silently create a ghost record if the ID
# was mistyped or already deleted.
@app.post("/v1/admin/quotes/{quote_id}/respond", status_code=200)
async def mark_responded(quote_id: str):
    try:
        get_table().update_item(
            Key={"id": quote_id},
            UpdateExpression="SET #s = :v",
            # "status" is a reserved word in DynamoDB, so we use an alias (#s)
            # to avoid a syntax error at runtime.
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":v": "Responded"},
            ConditionExpression="attribute_exists(id)",
        )
        return {"status": "success", "id": quote_id, "new_status": "Responded"}
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # The quote doesn't exist — return 404 rather than a generic 500
            # so the dashboard can show a meaningful "not found" message.
            raise HTTPException(status_code=404, detail="Quote not found.")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /health ────────────────────────────────────────────────────────────────
# Simple health check used to verify the Lambda function is alive and reachable.
# Returns a UTC timestamp so you can see how recently the function responded.
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Lambda entry point ─────────────────────────────────────────────────────────
# Mangum translates the Lambda event/context objects into an ASGI-compatible
# request that FastAPI understands, then converts FastAPI's response back into
# the format API Gateway expects. Without this adapter, FastAPI cannot run
# inside Lambda — it only speaks ASGI, not Lambda's native invocation protocol.
handler = Mangum(app, lifespan="off")
# lifespan="off" prevents Mangum from trying to run FastAPI's startup/shutdown
# lifecycle hooks, which aren't meaningful in a stateless Lambda environment.
