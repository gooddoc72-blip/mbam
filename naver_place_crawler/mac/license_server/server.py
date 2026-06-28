from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import os
from datetime import datetime

app = FastAPI(title="Crawler License Server")

DB_FILE = "server_authorized_hwids.json"

class VerifyRequest(BaseModel):
    hwid: str

class RegisterRequest(BaseModel):
    hwid: str
    username: str

class StatusUpdateRequest(BaseModel):
    hwid: str
    status: str

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@app.post("/verify")
def verify_hwid(req: VerifyRequest):
    db = load_db()
    if req.hwid not in db:
        return {"registered": False, "status": "unregistered", "authorized": False}
    
    device = db[req.hwid]
    device["last_accessed"] = datetime.now().isoformat()
    save_db(db)
    
    status = device.get("status", "pending")
    if status == "approved":
        return {"registered": True, "status": status, "authorized": True}
    else:
        return {"registered": True, "status": status, "authorized": False}

@app.post("/register")
def register_hwid(req: RegisterRequest):
    db = load_db()
    if req.hwid in db:
        return {"success": False, "message": "Already registered"}
    
    db[req.hwid] = {
        "username": req.username,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "last_accessed": datetime.now().isoformat()
    }
    save_db(db)
    return {"success": True, "status": "pending"}

@app.get("/admin/list")
def list_hwids():
    return load_db()

@app.post("/admin/update_status")
def update_status(req: StatusUpdateRequest):
    db = load_db()
    if req.hwid not in db:
        raise HTTPException(status_code=404, detail="HWID not found")
    if req.status not in ["pending", "approved", "revoked"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    db[req.hwid]["status"] = req.status
    save_db(db)
    return {"success": True, "hwid": req.hwid, "new_status": req.status}
