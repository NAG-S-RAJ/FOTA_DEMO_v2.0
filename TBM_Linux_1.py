import websocket
import json
import threading
import time
import requests
import urllib3
import hashlib
import os
import socket
import re

# ============================================================
# RASPBERRY PI DEVICE ID / VIN GENERATION
# ============================================================

hostname = socket.gethostname().upper()
hostname = re.sub(r'[^A-Z0-9]', '', hostname)

def get_device_id():
    """
    Get a unique device identifier for Raspberry Pi.
    Prefer Raspberry Pi product UUID if available.
    Otherwise use /etc/machine-id.
    """

    # Try product UUID
    uuid_path = "/sys/class/dmi/id/product_uuid"

    try:
        if os.path.exists(uuid_path):
            with open(uuid_path, "r") as f:
                device_id = f.read().strip()

            if device_id:
                return device_id

    except Exception:
        pass

    # Fallback to machine-id
    machine_id_path = "/etc/machine-id"

    try:
        with open(machine_id_path, "r") as f:
            device_id = f.read().strip()

        if device_id:
            return device_id

    except Exception:
        pass

    # Final fallback
    return socket.gethostname()


DEVICE_ID = get_device_id()

print("Device ID :", DEVICE_ID)

# Remove special characters
DEVICE_ID_CLEAN = re.sub(
    r'[^A-Z0-9]',
    '',
    DEVICE_ID.upper()
)

# Generate VIN
VIN = f"VH_{hostname}_{DEVICE_ID_CLEAN[-8:]}"

print("VIN :", VIN)


# ============================================================
# CONFIGURATION
# ============================================================

AUTH_SECRET = "FOTA_DEMO_SECRET"

SERVER_WS = "wss://fota-demo-v2-0.onrender.com/ws"

DOWNLOAD_DIR = "/home/pi/FirmwareFiles"

os.makedirs(
    DOWNLOAD_DIR,
    exist_ok=True
)

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

approved = False
rejected = False

print("SERVER_WS =", SERVER_WS)
print("DOWNLOAD_DIR =", DOWNLOAD_DIR)


# ============================================================
# HEARTBEAT
# ============================================================

def heartbeat(ws):

    while True:

        try:

            if approved:

                ws.send(
                    json.dumps({
                        "type": "heartbeat",
                        "vin": VIN
                    })
                )

        except Exception:

            break

        time.sleep(10)


# ============================================================
# SHA256
# ============================================================

def calculate_sha256(filepath):

    sha256 = hashlib.sha256()

    with open(filepath, "rb") as f:

        for chunk in iter(
            lambda: f.read(4096),
            b""
        ):

            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# CONNECTION OPEN
# ============================================================

def on_open(ws):

    print("\nVehicle Bootup")

    ws.send(
        json.dumps({
            "type": "register_request",
            "vin": VIN
        })
    )

    print("\nConnection request sent")

    threading.Thread(
        target=heartbeat,
        args=(ws,),
        daemon=True
    ).start()


# ============================================================
# RECEIVE MESSAGE
# ============================================================

def on_message(ws, message):

    global approved
    global rejected

    try:

        data = json.loads(message)

    except json.JSONDecodeError:

        print("Invalid JSON received:")
        print(message)

        return

    msg_type = data.get("type")

    # --------------------------------------------------------
    # AUTHENTICATION CHALLENGE
    # --------------------------------------------------------

    if msg_type == "challenge":

        print(
            "\nAuthentication Challenge Received"
        )

        challenge = data["challenge"]

        response = hashlib.sha256(
            (
                challenge +
                AUTH_SECRET
            ).encode()
        ).hexdigest()

        ws.send(
            json.dumps({
                "type": "auth_response",
                "vin": VIN,
                "response": response
            })
        )

    # --------------------------------------------------------
    # AUTHENTICATION PASSED
    # --------------------------------------------------------

    elif msg_type == "auth_passed":

        print(
            "\nAUTHENTICATION PASSED"
        )

        print(
            "Waiting for approval..."
        )

    # --------------------------------------------------------
    # APPROVED
    # --------------------------------------------------------

    elif msg_type == "approved":

        approved = True

        print(
            "\nVEHICLE CONNECTION APPROVED"
        )

        print(
            "Waiting for campaigns...\n"
        )

    # --------------------------------------------------------
    # REJECTED
    # --------------------------------------------------------

    elif msg_type == "rejected":

        rejected = True
        approved = False

        print(
            "\nConnection rejected"
        )

        ws.close()

    # --------------------------------------------------------
    # ALREADY CONNECTED
    # --------------------------------------------------------

    elif msg_type == "already_connected":

        print(
            "\nERROR: Another Vehicle with VIN",
            VIN,
            "is already connected."
        )

        ws.close()

    # --------------------------------------------------------
    # CAMPAIGN
    # --------------------------------------------------------

    elif msg_type == "campaign":

        print("\nCampaign received")

        campaign_id = data["campaign_id"]
        campaign_name = data["campaign_name"]
        target_ecu = data["target_ecu"]

        print(
            "Campaign :",
            campaign_name
        )

        print(
            "Target ECU :",
            target_ecu
        )

        # ----------------------------------------------------
        # CAMPAIGN ACK
        # ----------------------------------------------------

        ws.send(
            json.dumps({
                "type": "campaign_ack",
                "vin": VIN,
                "campaign_id": campaign_id
            })
        )

        try:

            # =================================================
            # SGW
            # =================================================

            if target_ecu in ["SGW", "BOTH"]:

                print(
                    "\nDownloading SGW Firmware..."
                )

                response = requests.get(
                    data["sgw_download_url"],
                    verify=False,
                    timeout=60
                )

                response.raise_for_status()

                sgw_path = os.path.join(
                    DOWNLOAD_DIR,
                    data["sgw_firmware"]
                )

                with open(
                    sgw_path,
                    "wb"
                ) as f:

                    f.write(response.content)

                print(
                    "SGW Firmware Saved :",
                    sgw_path
                )

                # SHA256 verification
                calculated_hash = calculate_sha256(
                    sgw_path
                )

                print(
                    "SGW SHA256 :",
                    calculated_hash
                )

                if calculated_hash != data["sgw_checksum"]:

                    print(
                        "\nSGW Checksum Failed"
                    )

                    ws.send(
                        json.dumps({
                            "type": "checksum_failed",
                            "vin": VIN,
                            "campaign_id": campaign_id
                        })
                    )

                    return

                print(
                    "SGW Checksum Passed"
                )

            # =================================================
            # BCM
            # =================================================

            if target_ecu in ["BCM", "BOTH"]:

                print(
                    "\nDownloading BCM Firmware..."
                )

                response = requests.get(
                    data["bcm_download_url"],
                    verify=False,
                    timeout=60
                )

                response.raise_for_status()

                bcm_path = os.path.join(
                    DOWNLOAD_DIR,
                    data["bcm_firmware"]
                )

                with open(
                    bcm_path,
                    "wb"
                ) as f:

                    f.write(response.content)

                print(
                    "BCM Firmware Saved :",
                    bcm_path
                )

                # SHA256 verification
                calculated_hash = calculate_sha256(
                    bcm_path
                )

                print(
                    "BCM SHA256 :",
                    calculated_hash
                )

                if calculated_hash != data["bcm_checksum"]:

                    print(
                        "\nBCM Checksum Failed"
                    )

                    ws.send(
                        json.dumps({
                            "type": "checksum_failed",
                            "vin": VIN,
                            "campaign_id": campaign_id
                        })
                    )

                    return

                print(
                    "BCM Checksum Passed"
                )

            # =================================================
            # DOWNLOAD COMPLETE
            # =================================================

            print(
                "\nFirmware Download Complete"
            )

            # =================================================
            # SIMULATE UPDATE PROGRESS
            # =================================================

            for progress in range(
                0,
                101,
                20
            ):

                time.sleep(1)

                ws.send(
                    json.dumps({
                        "type": "progress",
                        "vin": VIN,
                        "campaign_id": campaign_id,
                        "progress": progress
                    })
                )

                print(
                    "Update Progress :",
                    progress,
                    "%"
                )

            # =================================================
            # CAMPAIGN COMPLETE
            # =================================================

            completed = {

                "type": "completed",

                "vin": VIN,

                "campaign_id": campaign_id,

                "target_ecu": target_ecu
            }

            if target_ecu == "SGW":

                completed[
                    "sgw_version"
                ] = data[
                    "sgw_target_version"
                ]

            elif target_ecu == "BCM":

                completed[
                    "bcm_version"
                ] = data[
                    "bcm_target_version"
                ]

            else:

                completed[
                    "sgw_version"
                ] = data[
                    "sgw_target_version"
                ]

                completed[
                    "bcm_version"
                ] = data[
                    "bcm_target_version"
                ]

            ws.send(
                json.dumps(completed)
            )

            print(
                "\nCampaign completed"
            )

        except Exception as e:

            print(
                "\nDownload failed :",
                e
            )

    # --------------------------------------------------------
    # OTHER SERVER MESSAGE
    # --------------------------------------------------------

    else:

        print(
            "RX:",
            data
        )


# ============================================================
# ERROR
# ============================================================

def on_error(ws, error):

    print(
        "\nERROR:",
        error
    )


# ============================================================
# CLOSE
# ============================================================

def on_close(
    ws,
    code,
    msg
):

    global approved

    approved = False

    print(
        "\nDisconnected from server"
    )

    print(
        "Close code :",
        code
    )

    print(
        "Close message :",
        msg
    )


# ============================================================
# MAIN CONNECTION LOOP
# ============================================================

while True:

    try:

        approved = False
        rejected = False

        print(
            "\nConnecting to FOTA Server..."
        )

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

        print(
            "\nConnection Error:",
            e
        )

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