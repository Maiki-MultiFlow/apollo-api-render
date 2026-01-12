#!/usr/bin/env python3
"""
REST API Wrapper for Apollo MCP Server - Render Deployment
Simplified version focusing on working endpoints (CRM operations)
"""
import os
import logging
import urllib.parse
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("apollo-api")

# Initialize FastAPI
app = FastAPI(
    title="Apollo API for n8n",
    description="Apollo CRM operations via REST API",
    version="1.0.0"
)

# Add CORS for n8n
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for your n8n instance in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration - Your Apollo API key
API_TOKEN = os.environ.get("APOLLO_API_TOKEN", "rLM79N_1aVD1DNVrQ4jH_Q")
BASE_URL = "https://api.apollo.io/api/v1"

# Pydantic Models
class CreateContactRequest(BaseModel):
    email: str = Field(..., description="Contact email (required)")
    first_name: Optional[str] = Field("", description="First name")
    last_name: Optional[str] = Field("", description="Last name")
    title: Optional[str] = Field("", description="Job title")
    company: Optional[str] = Field("", description="Company name")
    phone: Optional[str] = Field("", description="Phone number")

class UpdateContactRequest(BaseModel):
    contact_id: str = Field(..., description="Apollo contact ID")
    email: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None

# Helper function
async def make_apollo_request(method: str, endpoint: str, query_params=None, body_data=None):
    """Make authenticated request to Apollo API."""
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "x-api-key": API_TOKEN
    }
    
    url = f"{BASE_URL}{endpoint}"
    if query_params:
        # Build query string
        params = []
        for key, value in query_params.items():
            if value is not None and value != "":
                params.append(f"{key}={urllib.parse.quote(str(value))}")
        if params:
            url = f"{url}?{'&'.join(params)}"
    
    logger.info(f"Making {method} request to: {url}")
    
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                response = await client.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=body_data, timeout=30)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=body_data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo API error: {e.response.status_code}")
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Apollo API error: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "status": "online",
        "service": "Apollo API Wrapper for n8n",
        "endpoints": {
            "create_contact": "POST /api/create-contact",
            "update_contact": "PUT /api/update-contact",
            "check_status": "GET /api/status",
            "health": "GET /health"
        },
        "note": "Search and enrichment endpoints require paid Apollo plan"
    }

@app.get("/health")
async def health_check():
    """Health check for Render."""
    return {"status": "healthy", "api_configured": bool(API_TOKEN)}

@app.get("/api/status")
async def check_status():
    """Check Apollo API connection status."""
    try:
        headers = {"x-api-key": API_TOKEN}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/auth/health",
                headers=headers,
                timeout=10
            )
            
            return {
                "apollo_status": "connected" if response.status_code == 200 else "error",
                "status_code": response.status_code,
                "is_logged_in": response.json().get("is_logged_in", False) if response.status_code == 200 else False
            }
    except Exception as e:
        return {"apollo_status": "error", "error": str(e)}

@app.post("/api/create-contact")
async def create_contact(request: CreateContactRequest):
    """Create a new contact in Apollo CRM."""
    try:
        # Build query params for Apollo
        query_params = {
            "email": request.email,
            "first_name": request.first_name,
            "last_name": request.last_name,
            "title": request.title,
            "organization_name": request.company,
            "direct_phone": request.phone
        }
        
        # Remove empty values
        query_params = {k: v for k, v in query_params.items() if v}
        
        data = await make_apollo_request("POST", "/contacts", query_params=query_params)
        
        # Format response for n8n
        contact = data.get("contact", {})
        return {
            "success": True,
            "contact_id": contact.get("id"),
            "name": contact.get("name"),
            "email": contact.get("email"),
            "title": contact.get("title"),
            "company": contact.get("organization_name") or contact.get("account", {}).get("name"),
            "raw_response": contact
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/update-contact")
async def update_contact(request: UpdateContactRequest):
    """Update an existing contact in Apollo CRM."""
    try:
        body_data = {}
        if request.email:
            body_data["email"] = request.email
        if request.title:
            body_data["title"] = request.title
        if request.phone:
            body_data["direct_phone"] = request.phone
        if request.linkedin_url:
            body_data["linkedin_url"] = request.linkedin_url
        
        if not body_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        endpoint = f"/contacts/{request.contact_id}"
        data = await make_apollo_request("PUT", endpoint, body_data=body_data)
        
        contact = data.get("contact", {})
        return {
            "success": True,
            "contact_id": contact.get("id"),
            "updated_fields": list(body_data.keys()),
            "raw_response": contact
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Simple webhook endpoint for n8n
@app.post("/webhook/n8n")
async def n8n_webhook(data: dict):
    """Generic webhook endpoint for n8n."""
    action = data.get("action")
    
    if action == "create_contact":
        return await create_contact(CreateContactRequest(**data.get("params", {})))
    elif action == "update_contact":
        return await update_contact(UpdateContactRequest(**data.get("params", {})))
    elif action == "status":
        return await check_status()
    else:
        return {"error": "Unknown action", "available": ["create_contact", "update_contact", "status"]}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

### File 2: `requirements.txt`
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
httpx==0.25.2
pydantic==2.5.2
```

### File 3: `.gitignore`
```
__pycache__/
*.py[cod]
.env
.venv/
venv/