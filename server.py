from urllib import response
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    PlainTextResponse,
    Response
)
from datetime import datetime
from zoneinfo import ZoneInfo
import uvicorn
import json
import hashlib
import time
import requests
import base64
import json
import psycopg2
from psycopg2 import OperationalError, InterfaceError
import os
import secrets

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

app = FastAPI()
DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

AUTH_SECRET = "FOTA_DEMO_SECRET"
pending_auth = {}

conn = None
cursor = None

def connect_db():
    global conn, cursor

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    print("Database connected")


def ensure_connection():
    global conn, cursor

    try:
        if conn is None or conn.closed:
            connect_db()
            return

        if cursor is None or cursor.closed:
            cursor = conn.cursor()
            return

        cursor.execute("SELECT 1")

    except Exception as e:
        print(f"DB reconnect: {e}")
        connect_db()

# Initial connection
connect_db()

cursor.execute("""
CREATE TABLE IF NOT EXISTS registered_tbms (

    vin VARCHAR(50) PRIMARY KEY,

    sgw_version VARCHAR(50),

    bcm_version VARCHAR(50),

    added_on TIMESTAMPTZ

)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS campaigns(

    campaign_id VARCHAR(100) PRIMARY KEY,

    vin VARCHAR(50),

    target_ecu VARCHAR(20),

    campaign_name VARCHAR(200),

    sgw_target_version VARCHAR(50),

    bcm_target_version VARCHAR(50),

    sgw_firmware VARCHAR(255),

    bcm_firmware VARCHAR(255),

    status VARCHAR(50)

)
""")

conn.commit()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

pending_tbms = {}
connected_tbms = {}
logs = []

def get_sha256(filepath):

    sha256 = hashlib.sha256()

    with open(filepath, "rb") as f:

        for chunk in iter(
            lambda: f.read(4096),
            b""
        ):
            sha256.update(chunk)

    return sha256.hexdigest()

def add_log(msg):

    print(msg)

    logs.append(msg)

    if len(logs) > 500:
        logs.pop(0)

# GITHUB Firware repo endpoints and functions

@app.get("/github_test")
def github_test():

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(
        "https://api.github.com/user",
        headers=headers
    )

    return response.json()

def upload_to_github(path, content):

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    data = {
        "message": f"Upload {path}",
        "content": base64.b64encode(content).decode(),
        "branch": GITHUB_BRANCH
    }

    response = requests.put(
        url,
        headers=headers,
        json=data
    )

    print("UPLOAD STATUS:", response.status_code)
    print("UPLOAD BODY:", response.text)

    return response.json()

def read_latest_json():

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/contents/latest.json"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    r = requests.get(url, headers=headers)

    if r.status_code == 404:
        return {}, None

    r.raise_for_status()

    data = r.json()

    latest = json.loads(
        base64.b64decode(data["content"]).decode()
    )

    return latest, data["sha"]

def update_latest_json(data, sha):

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/contents/latest.json"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    body = {
        "message": "Update latest firmware",
        "content": base64.b64encode(
            json.dumps(data, indent=4).encode()
        ).decode(),
        "branch": GITHUB_BRANCH
    }
    
    if sha:
        body["sha"] = sha
    
    r = requests.put(
        url,
        headers=headers,
        json=body
    )
    
    print("LATEST STATUS:", r.status_code)
    print("LATEST BODY:", r.text)

def github_list(path):

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}"
        f"/contents/{path}"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(
        url,
        headers=headers
    )

    response.raise_for_status()

    return response.json()

@app.post("/upload_firmware")
async def upload_firmware(
    ecu: str,
    version: str,
    file: UploadFile = File(...)
):

    content = await file.read()
    version = f"{float(version):.1f}"
    filename = f"{ecu}_v{version}.bin"
    uploaded_at = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p")
    github_path = f"firmware/{ecu}/{filename}"

    result = upload_to_github(
        github_path,
        content
    )
    
    if "content" not in result:
    
        return {
            "status": "error",
            "github": result
        }
    
    latest, sha = read_latest_json()
    
    latest[ecu] = {
    
        "version": version,
    
        "file": github_path,

        "path": f"firmware/{ecu}/{filename}",
    
        "download_url": result["content"]["download_url"],

        "uploaded_at": uploaded_at
    
    }
    
    update_latest_json(
        latest,
        sha
    )
    
    return {
    
        "status": "success",
    
        "file": filename,

        "path": f"firmware/{ecu}/{filename}",
    
        "github": result
    
    }

@app.get("/latest_firmware")
async def latest_firmware():

    try:

        latest, _ = read_latest_json()

        return latest

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }

def version_key(item):
    try:
        return (item["ecu"], float(item.get("version", 0)))
    except (ValueError, TypeError):
        return (item["ecu"], 0.0)
    
@app.get("/firmware_history")
async def firmware_history():

    try:

        history = []

        for ecu in ["SGW", "BCM"]:

            files = github_list(
                f"firmware/{ecu}"
            )

            if not isinstance(files, list):
                continue

            for file in files:

                if file["type"] != "file":
                    continue

                filename = file["name"]

                version = ""

                if "_v" in filename:

                    version = (
                        filename
                        .split("_v")[1]
                        .replace(".bin", "")
                    )

                history.append({

                    "ecu": ecu,

                    "version": version,

                    "file": filename,

                    "path": f"firmware/{ecu}/{filename}",

                    "download_url": file["download_url"]

                })

        history.sort(
            key=version_key,
            reverse=True
            )

        return history

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/download_firmware")
async def download_firmware(path: str):

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.raw"
    }

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        raise HTTPException(
            status_code=404,
            detail=f"GitHub returned {r.status_code}: {r.text}"
        )

    return Response(
        content=r.content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition":
            f'attachment; filename="{os.path.basename(path)}"'
        }
    )

#----------------------------------------------------------------

@app.delete("/campaign/{campaign_id}")
async def delete_campaign(campaign_id: str):

    ensure_connection()

    cursor.execute(
        """
        DELETE FROM campaigns
        WHERE campaign_id = %s
        """,
        (campaign_id,)
    )

    conn.commit()

    add_log(
        f"Campaign Deleted: {campaign_id}"
    )

    return {"status": "deleted"}

@app.delete("/registered_tbm/{vin}")
async def delete_registered_tbm(
    vin: str
):  
    ensure_connection()

    cursor.execute(
        """
        DELETE
        FROM registered_tbms
        WHERE vin=%s
        """,
        (vin,)
    )

    conn.commit()

    add_log(
        f"Vehicle Deleted: {vin}"
    )

    return {
        "status": "deleted"
    }

# ======================
# BASIC APIS
# ======================
@app.get("/registered_tbm/{vin}")
async def get_tbm(
    vin: str
):
    ensure_connection()
    cursor.execute("""

    SELECT

    vin,

    sgw_version,

    bcm_version

    FROM registered_tbms

    WHERE vin = %s

    """,

    (vin,)
    )

    row = cursor.fetchone()

    if not row:

        return {
            "status": "not_found"
        }

    return {

    "vin": row[0],

    "sgw_version": row[1],

    "bcm_version": row[2]

}


@app.get("/")
async def root():

    return {
        "status": "running"
    }


@app.get("/pending")
async def pending():

    return {
        "pending": list(
            pending_tbms.keys()
        )
    }


@app.get("/tbms")
async def tbms():

    return {
        "online_tbms": list(
            connected_tbms.keys()
        )
    }

@app.get("/download_logs")
async def download_logs():

    return PlainTextResponse(
        "\n".join(logs),
        headers={
            "Content-Disposition":
            "attachment; filename=fota_logs.txt"
        }
    )

@app.get("/logs")
async def get_logs():

    return logs


@app.get("/campaigns")
async def get_campaigns():

    ensure_connection()

    cursor.execute("""
        SELECT
            campaign_id,
            vin,
            target_ecu,
            campaign_name,
            sgw_target_version,
            bcm_target_version,
            sgw_firmware,
            bcm_firmware,
            status
        FROM campaigns
    """)

    rows = cursor.fetchall()

    return [
        {
            "campaign_id":row[0],
            "vin":row[1],
            "target_ecu":row[2],
            "campaign_name":row[3],
            "sgw_target_version":row[4],
            "bcm_target_version":row[5],
            "sgw_firmware":row[6],
            "bcm_firmware":row[7],
            "status":row[8]
        }       
        for row in rows
    ]


# ======================
# FILE UPLOAD
# ======================
@app.post("/register_tbm")
async def register_tbm(
    vin: str,
    sgw_version: str,
    bcm_version: str
):
    ensure_connection()
    try:
        
        cursor.execute(
            """
            INSERT INTO registered_tbms
            (
                vin,
                sgw_version,
                bcm_version,
                added_on
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                vin,
                sgw_version,
                bcm_version,
                datetime.now(ZoneInfo("Asia/Kolkata"))
            )
        )

        conn.commit()

        add_log(
            f"Vehicle Registered: {vin}"
        )

        return {
            "status": "success"
        }

    except psycopg2.IntegrityError:

        conn.rollback()

        return {
            "status": "already_exists"
        }

@app.post("/upload")
async def upload(
    file: UploadFile = File(...)
):

    path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    with open(path, "wb") as f:

        f.write(
            await file.read()
        )

    add_log(
        f"Firmware Uploaded: {file.filename}"
    )

    return {
        "status": "success",
        "file": file.filename
    }

@app.get("/registered_tbms")
async def get_registered_tbms():
    ensure_connection()
    cursor.execute("""
    SELECT

        vin,

        sgw_version,

        bcm_version,

        added_on

    FROM registered_tbms

    ORDER BY added_on DESC

    """)

    rows = cursor.fetchall()

    result = []

    for row in rows:

        result.append({

            "vin": row[0],

            "sgw_version": row[1],

            "bcm_version": row[2],

            "added_on": row[3]

        })

    return result

@app.get("/files/{filename}")
async def file_download(
    filename: str
):

    path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    return FileResponse(
        path,
        filename=filename
    )


# ======================
# APPROVE / REJECT
# ======================

@app.post("/approve/{vin}")
async def approve(vin: str):

    if vin not in pending_tbms:

        return {
            "status": "not_found"
        }

    ws = pending_tbms[vin]
    
    try:
        ensure_connection()
        cursor.execute(
            """
            INSERT INTO registered_tbms
            (
                vin,
                sgw_version,
                bcm_version,
                added_on
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT (vin)
            DO NOTHING
            """,
            (
                vin,
                "1.0",
                "1.0",
                datetime.now(ZoneInfo("Asia/Kolkata"))
            )
        )

        conn.commit()

    except Exception as e:

        add_log(
            f"Database Error: {e}"
        )

        return {
            "status": "db_error",
            "message": str(e)
        }

    del pending_tbms[vin]

    connected_tbms[vin] = ws

    await ws.send_text(
        json.dumps({
            "type": "approved"
        })
    )

    add_log(
        f"{vin} approved and registered"
    )

    return {
        "status": "approved"
    }


@app.post("/reject/{vin}")
async def reject(vin: str):

    if vin not in pending_tbms:

        return {
            "status": "not_found"
        }

    ws = pending_tbms[vin]

    await ws.send_text(
        json.dumps({
            "type": "rejected"
        })
    )

    await ws.close()

    del pending_tbms[vin]

    add_log(
        f"{vin} rejected"
    )

    return {
        "status": "rejected"
    }


# ======================
# CREATE CAMPAIGN
# ======================

@app.post("/campaign")
async def campaign(

    campaign_id:str,

    vin:str,

    campaign_name:str,

    sgw_target_version:str="",

    bcm_target_version:str="",

    sgw_firmware:str="",

    bcm_firmware:str=""

):

    if vin not in connected_tbms:

        ensure_connection()
    
        cursor.execute(
            """
            SELECT 1
            FROM registered_tbms
            WHERE vin=%s
            """,
            (vin,)
        )
    
        if cursor.fetchone() is None:
            return {
                "status":"error",
                "message":"VIN not registered"
            }
    
        return {
            "status":"VEHICLE_NOT_CONNECTED"
        }

    campaign_id = campaign_id.strip()

    if not campaign_id:
        return {
            "status": "error",
            "message": "Campaign ID is required"
        }
    
    ensure_connection()

    cursor.execute(
        """
        SELECT campaign_id
        FROM campaigns
        WHERE campaign_id=%s
        """,
        (campaign_id,)
    )

    if cursor.fetchone():

        return {
            "status": "error",
            "message": "Campaign ID already exists"
        }

    if sgw_firmware and bcm_firmware:
    
        target_ecu = "BOTH"
    
    elif sgw_firmware:
    
        target_ecu = "SGW"
    
    elif bcm_firmware:
    
        target_ecu = "BCM"
    
    else:
    
        return {
        
            "status":"error",
    
            "message":"Select at least one ECU"
    
        }

    if target_ecu == "SGW":

        if not sgw_target_version:
            return {
                "status":"error",
                "message":"SGW target version is required"
            }

        if not sgw_firmware:
            return {
                "status":"error",
                "message":"SGW firmware is required"
            }

    elif target_ecu == "BCM":

        if not bcm_target_version:
            return {
                "status":"error",
                "message":"BCM target version is required"
            }

        if not bcm_firmware:
            return {
                "status":"error",
                "message":"BCM firmware is required"
            }

    elif target_ecu == "BOTH":

        if (
            not sgw_target_version or
            not bcm_target_version or
            not sgw_firmware or
            not bcm_firmware
        ):
            return {
                "status":"error",
                "message":"Both firmware files and versions are required"
            }

    base_url = os.getenv(
        "PUBLIC_URL",
        "https://fota-demo-v2-0.onrender.com"
    )
    sgw_download_url = ""
    bcm_download_url = ""
    sgw_checksum = ""
    bcm_checksum = ""
    if sgw_firmware:

        sgw_download_url = (
            f"{base_url}/files/{sgw_firmware}"
        )

    if bcm_firmware:

        bcm_download_url = (
            f"{base_url}/files/{bcm_firmware}"
        )
    if sgw_firmware:
            
        path = os.path.join(
            UPLOAD_FOLDER,
            sgw_firmware
        )
        if not os.path.exists(path):
            return {
                "status":"error",
                "message":"SGW firmware not found"
            }

        sgw_checksum = get_sha256(path)
    
    if bcm_firmware:

        path = os.path.join(
            UPLOAD_FOLDER,
            bcm_firmware
        )
        if not os.path.exists(path):
            return {
                "status":"error",
                "message":"BCM firmware not found"
            }

        bcm_checksum = get_sha256(path)

    ensure_connection()
    try:
        cursor.execute(
            """
            INSERT INTO campaigns
            (
                campaign_id,
                vin,
                target_ecu,
                campaign_name,
                sgw_target_version,
                bcm_target_version,
                sgw_firmware,
                bcm_firmware,
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                campaign_id,
                vin,
                target_ecu,
                campaign_name,
                sgw_target_version,
                bcm_target_version,
                sgw_firmware,
                bcm_firmware,
                "sent"
            )
        )

        conn.commit()

    except Exception as e:

        conn.rollback()

        return {
            "status":"error",
            "message":str(e)
        }

    ws = connected_tbms[vin]

    try:
        await ws.send_text(json.dumps({

            "type":"campaign",

            "campaign_id":campaign_id,

            "target_ecu":target_ecu,

            "campaign_name":campaign_name,

            "sgw_target_version":sgw_target_version,

            "bcm_target_version":bcm_target_version,

            "sgw_firmware":sgw_firmware,

            "bcm_firmware":bcm_firmware,

            "sgw_download_url":sgw_download_url,

            "bcm_download_url":bcm_download_url,

            "sgw_checksum":sgw_checksum,

            "bcm_checksum":bcm_checksum

        }))
    except Exception:

        cursor.execute(
            """
            UPDATE campaigns
            SET status='send_failed'
            WHERE campaign_id=%s
            """,
            (campaign_id,)
        )
    
        conn.commit()
    
        return {
            "status":"send_failed"
        }

    add_log(
        f"Campaign Sent -> {vin}"
    )

    return {
        "status": "sent"
    }


# ======================
# WEBSOCKET
# ======================

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):

    await websocket.accept()

    vin = None

    try:

        while True:

            raw = await websocket.receive_text()

            add_log(
                f"RX: {raw}"
            )

            data = json.loads(raw)

            msg_type = data.get(
                "type"
            )

            if msg_type == "register_request":

                vin = data["vin"]

                challenge = secrets.token_hex(16)

                pending_auth[vin] = {
                
                    "challenge": challenge,

                    "timestamp": time.time()

                }

                await websocket.send_text(
                    json.dumps({
                    
                        "type": "challenge",

                        "challenge": challenge

                    })
                )

                add_log(
                    f"Challenge sent -> {vin}"
                )

            elif msg_type == "auth_response":

               vin = data["vin"]

               response = data["response"]

               if vin not in pending_auth:

                   await websocket.close()

                   continue
               
               challenge = pending_auth[vin]["challenge"]

               if time.time() - pending_auth[vin]["timestamp"] > 60:

                   add_log(
                       f"{vin} auth timeout"
                   )

                   del pending_auth[vin]

                   await websocket.close()

                   continue
               
               expected = hashlib.sha256(

                   (
                       challenge +
                       AUTH_SECRET
                   ).encode()

               ).hexdigest()

               if response != expected:

                   add_log(
                       f"{vin} authentication failed"
                   )

                   del pending_auth[vin]

                   await websocket.send_text(
                       json.dumps({
                           "type":"auth_failed"
                       })
                   )

                   await websocket.close()

                   continue
               
               await websocket.send_text(
                       json.dumps({
                           "type":"auth_passed"
                       })
                   )
               add_log(
                   f"{vin} authentication passed"
               )

               del pending_auth[vin]

               ensure_connection()

               cursor.execute(
                   """
                   SELECT vin
                   FROM registered_tbms
                   WHERE vin=%s
                   """,
                   (vin,)
               )

               row = cursor.fetchone()

               if row:

                   # Prevent duplicate VIN connections
                   if vin in connected_tbms:
                    
                        await websocket.send_text(
                            json.dumps({
                                "type": "already_connected"
                            })
                        )
                
                        add_log(
                            f"Duplicate connection rejected -> {vin}"
                        )
                
                        await websocket.close()
                
                        return

                   connected_tbms[vin] = websocket

                   await websocket.send_text(
                       json.dumps({
                           "type":"approved"
                       })
                   )

                   add_log(
                       f"{vin} auto-approved"
                   )

               else:

                   pending_tbms[vin] = websocket

                   add_log(
                       f"{vin} pending approval"
                   )

            elif msg_type == "heartbeat":

                add_log(
                    f"Heartbeat Received -> {vin}"
                )

            elif msg_type == "campaign_ack":

                ensure_connection()

                cursor.execute(
                    """
                    UPDATE campaigns
                    SET status=%s
                    WHERE campaign_id=%s
                    """,
                    (
                        "acknowledged",
                        data["campaign_id"]
                    )
                )

                conn.commit()

                add_log(
                    f"{vin} campaign acknowledged"
                )

            elif msg_type == "progress":

                ensure_connection()

                cursor.execute(
                    """
                    UPDATE campaigns
                    SET status=%s
                    WHERE campaign_id=%s
                    """,
                    (
                        f"Downloading {data['progress']}%",
                        data["campaign_id"]
                    )
                )

                conn.commit()

                add_log(
                    f"{vin} progress {data['progress']}%"
                )

            elif msg_type == "completed":

                ensure_connection()
            
                if data["target_ecu"] == "SGW":
                
                    cursor.execute(
                        """
                        UPDATE registered_tbms
                        SET sgw_version=%s
                        WHERE vin=%s
                        """,
                        (
                            data["sgw_version"],
                            vin
                        )
                    )
            
                elif data["target_ecu"] == "BCM":
                
                    cursor.execute(
                        """
                        UPDATE registered_tbms
                        SET bcm_version=%s
                        WHERE vin=%s
                        """,
                        (
                            data["bcm_version"],
                            vin
                        )
                    )
            
                elif data["target_ecu"] == "BOTH":
                
                    cursor.execute(
                        """
                        UPDATE registered_tbms
                        SET
                            sgw_version=%s,
                            bcm_version=%s
                        WHERE vin=%s
                        """,
                        (
                            data["sgw_version"],
                            data["bcm_version"],
                            vin
                        )
                    )
            
                cursor.execute(
                    """
                    UPDATE campaigns
                    SET status=%s
                    WHERE campaign_id=%s
                    """,
                    (
                        "completed",
                        data["campaign_id"]
                    )
                )
            
                conn.commit()
            
                add_log(
                    f"{vin} {data['target_ecu']} update completed"
                )

            elif msg_type == "checksum_failed":

                ensure_connection()

                cursor.execute(
                    """
                    UPDATE campaigns
                    SET status=%s
                    WHERE campaign_id=%s
                    """,
                    (
                        "checksum_failed",
                        data["campaign_id"]
                    )
                )

                conn.commit()
            
            elif msg_type == "status_response":

                add_log(
                    f"{vin}: "
                    f"{data['status']}"
                )

    except WebSocketDisconnect:

        add_log(
            f"{vin} disconnected"
        )

    finally:

        if vin:
        
            if vin in pending_tbms:
            
                if pending_tbms[vin] is websocket:
                
                    del pending_tbms[vin]
    
                    add_log(
                        f"Removed pending {vin}"
                    )
    
            if vin in connected_tbms:
            
                if connected_tbms[vin] is websocket:
                
                    del connected_tbms[vin]
    
                    add_log(
                        f"Removed connected {vin}"
                    )


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            8000
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
