import websocket
import json
import threading
import time
import requests
import urllib3
import hashlib
import os

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

VIN = "FOTA0002"

DOWNLOAD_DIR = r"C:\FirmwareFiles"
os.makedirs(
    DOWNLOAD_DIR,
    exist_ok=True
)

# CHANGE THIS
SERVER_WS = "wss://fota-demo.onrender.com/ws"

approved = False
print("SERVER_WS =", SERVER_WS)

def heartbeat(ws):
    while True:
        try:
            if approved:
                ws.send(json.dumps({
                    "type": "heartbeat",
                    "vin": VIN
                }))
        except:
            break

        time.sleep(10)

def calculate_sha256(filepath):

    sha256 = hashlib.sha256()

    with open(filepath, "rb") as f:

        for chunk in iter(
            lambda: f.read(4096),
            b""
        ):
            sha256.update(chunk)

    return sha256.hexdigest()

def on_open(ws):

    print("\nTBM Bootup")

    ws.send(json.dumps({
        "type": "register_request",
        "vin": VIN
    }))

    print("\nConnection request sent\n"
          "Waiting for approval...")

    threading.Thread(
        target=heartbeat,
        args=(ws,),
        daemon=True
    ).start()


def on_message(ws, message):

    global approved

    data = json.loads(message)

    print("RX:", data)

    msg_type = data.get("type")

    if msg_type == "approved":

        approved = True

        print("\nTBM APPROVED")
        print("Waiting for campaigns...\n")

    elif msg_type == "rejected":

        global rejected
        rejected = True
        print("\nConnection rejected")
        ws.close()

    elif msg_type == "campaign":

        print("\nCampaign received")
        campaign_id = data["campaign_id"]
        campaign_name = data["campaign_name"]
        firmware_file = data["firmware_file"]
        download_url = data["download_url"]
        checksum = data["checksum"]

        print("Campaign :", campaign_name)
        print("Firmware :", firmware_file)

        ws.send(json.dumps({
            "type": "campaign_ack",
            "vin": VIN,
            "campaign_id": campaign_id
        }))

        try:

            print("\nDownloading firmware...")

            response = requests.get(
                download_url,
                verify=False)

            file_path = os.path.join(
                DOWNLOAD_DIR,
                firmware_file)

            with open(file_path, "wb") as f:
                f.write(response.content)

            print(
                "\nFirmware saved to:",
                file_path
            )

            received_checksum = calculate_sha256(
                file_path)
            
            if received_checksum != checksum:
            
                print(
                    "\nCHECKSUM VALIDATION FAILED"
                )
            
                ws.send(json.dumps({
                    "type": "checksum_failed",
                    "vin": VIN,
                    "campaign_id": campaign_id
                }))
            
                return
            
            print("\nCHECKSUM VALIDATION PASSED")
            print("\nDownload completed")

            for progress in range(0, 101, 20):

                time.sleep(1)

                ws.send(json.dumps({
                    "type": "progress",
                    "vin": VIN,
                    "campaign_id": campaign_id,
                    "progress": progress
                }))

            ws.send(json.dumps({
                "type": "completed",
                "vin": VIN,
                "campaign_id": campaign_id
            }))

            print("\nCampaign completed")

        except Exception as e:

            print("\nDownload failed:", e)


def on_error(ws, error):
    print("\nERROR:", error)


def on_close(ws, code, msg):

    global approved

    approved = False

    print("\nDisconnected from server")

while True:

    try:

        approved = False
        rejected = False

        print("\nConnecting to FOTA Server...")

        ws = websocket.WebSocketApp(
            SERVER_WS,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        ws.run_forever(
            ping_interval=20,
            ping_timeout=10
        )

    except Exception as e:

        print("\nConnection Error:", e)

    if rejected:

        print(
            "\nRequest rejected.\n"
            "Retrying registration in 10 seconds..."
        )

        time.sleep(10)

    else:

        print(
            "\nConnection lost.\n"
            "Retrying in 5 seconds..."
        )

        time.sleep(5)