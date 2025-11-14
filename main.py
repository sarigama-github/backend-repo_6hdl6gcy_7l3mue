import os
from datetime import datetime, timezone
from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Voting App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

# Pydantic models for requests

AllowedCategory = Literal["websites", "tools", "apps", "ideas", "misc"]

class ItemCreate(BaseModel):
    title: str
    category: AllowedCategory
    description: Optional[str] = None
    image: Optional[str] = None
    link: Optional[str] = None

class VoteRequest(BaseModel):
    direction: Literal["up", "down"]
    session_id: Optional[str] = None
    user_id: Optional[str] = None

# Routes

@app.get("/")
def root():
    return {"message": "Voting App API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_name"] = db.name
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

@app.post("/api/items")
def create_item(payload: ItemCreate):
    data = payload.model_dump()
    data.update({
        "upvotes": 0,
        "downvotes": 0,
        "score": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    inserted_id = db["votingitem"].insert_one(data).inserted_id
    return {"id": str(inserted_id)}

@app.get("/api/items")
def list_items(category: Optional[AllowedCategory] = None, sort: Optional[str] = "trending"):
    q = {}
    if category:
        q["category"] = category
    sort_spec = [("score", -1)]
    if sort == "newest":
        sort_spec = [("created_at", -1)]
    elif sort == "most":
        sort_spec = [("upvotes", -1)]
    # trending: score desc + recent boost
    items = list(db["votingitem"].find(q).sort(sort_spec))
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.get("/api/items/{item_id}")
def get_item(item_id: str):
    doc = db["votingitem"].find_one({"_id": oid(item_id)})
    if not doc:
        raise HTTPException(404, "Item not found")
    doc["id"] = str(doc.pop("_id"))
    return doc

@app.post("/api/items/{item_id}/vote")
def vote_item(item_id: str, vote: VoteRequest):
    # Prevent duplicate votes: one vote per (session_id or user_id) per item
    if not vote.session_id and not vote.user_id:
        raise HTTPException(400, "Missing session or user identifier")

    voter_filter = {
        "item_id": item_id,
        "$or": [
            {"session_id": vote.session_id} if vote.session_id else {"session_id": None},
            {"user_id": vote.user_id} if vote.user_id else {"user_id": None},
        ]
    }
    # Cleanup None in $or
    voter_filter["$or"] = [cond for cond in voter_filter["$or"] if list(cond.values())[0] is not None]

    existing = db["vote"].find_one(voter_filter)
    if existing:
        raise HTTPException(409, "Already voted")

    # Record the vote
    create_document("vote", {
        "item_id": item_id,
        "direction": vote.direction,
        "session_id": vote.session_id,
        "user_id": vote.user_id,
    })

    # Update counts on the item
    inc = {"upvotes": 1, "score": 1} if vote.direction == "up" else {"downvotes": 1, "score": -1}
    res = db["votingitem"].update_one({"_id": oid(item_id)}, {"$inc": inc, "$set": {"updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(404, "Item not found")

    doc = db["votingitem"].find_one({"_id": oid(item_id)})
    doc["id"] = str(doc.pop("_id"))
    return doc

@app.get("/api/stats")
def stats():
    # Simple trending: top 5 by score
    top = list(db["votingitem"].find({}).sort([("score", -1)]).limit(5))
    for t in top:
        t["id"] = str(t.pop("_id"))
    return {
        "top": top,
        "counts": {
            "total_items": db["votingitem"].count_documents({}),
            "total_votes": db["vote"].count_documents({}),
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
