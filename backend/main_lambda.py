"""
LPD&M Cleaning Solutions — Quote API (AWS Lambda + DynamoDB)
============================================================
Deployed via: AWS Lambda + API Gateway HTTP API
Database:     DynamoDB table  →  lpdm-quotes
Handler:      main_lambda.handler
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel
from typing import Optional
from botocore.exceptions import ClientError
import boto3
import uuid
from datetime import datetime, timezone

app = FastAPI(title="LPD&M Quote API", version="3.0.0")

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

TABLE_NAME = "lpdm-quotes"


def get_table():
    return boto3.resource("dynamodb", region_name="eu-west-2").Table(TABLE_NAME)


# ── Models ────────────────────────────────────────────────────────────────────

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
    submitted_at:     Optional[str] = None   # ignored — server sets this


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/v1/quote", status_code=201)
async def receive_quote(req: QuoteRequest):
    quote_id = str(uuid.uuid4())
    item = {
        "id":               quote_id,
        "name":             req.name,
        "email":            req.email,
        "phone":            req.phone,
        "service":          req.service,
        "property_size":    req.property_size  or "",
        "message":          req.message        or "",
        "submitted_at":     datetime.now(timezone.utc).isoformat(),
        "preferred_date":   req.preferred_date  or "",
        "referral_source":  req.referral_source or "",
        "status":           "New",
    }
    try:
        get_table().put_item(Item=item)
        return {"status": "success", "id": quote_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/admin/quotes")
async def list_quotes():
    try:
        resp  = get_table().scan()
        items = resp.get("Items", [])
        items.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/admin/quotes/{quote_id}")
async def get_quote(quote_id: str):
    try:
        resp = get_table().get_item(Key={"id": quote_id})
        item = resp.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="Quote not found.")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/admin/quotes/{quote_id}/respond", status_code=200)
async def mark_responded(quote_id: str):
    try:
        get_table().update_item(
            Key={"id": quote_id},
            UpdateExpression="SET #s = :v",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":v": "Responded"},
            ConditionExpression="attribute_exists(id)",
        )
        return {"status": "success", "id": quote_id, "new_status": "Responded"}
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(status_code=404, detail="Quote not found.")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Lambda entry point ────────────────────────────────────────────────────────
handler = Mangum(app, lifespan="off")
