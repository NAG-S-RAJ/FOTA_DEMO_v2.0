const SERVER = "https://fota-demo.onrender.com";

async function uploadFirmware(file) {

    const formData = new FormData();

    formData.append(
        "file",
        file
    );

    const response = await fetch(
        SERVER + "/upload",
        {
            method: "POST",
            body: formData
        }
    );

    return await response.json();
}

async function createCampaign() {

    const campaignId =
        document.getElementById(
            "campaignId"
        ).value.trim();

    const vin =
        document.getElementById(
            "vin"
        ).value.trim();

    const campaignName =
        document.getElementById(
            "campaignName"
        ).value.trim();

    const enableSGW =
        document.getElementById(
            "enableSGW"
        ).checked;

    const enableBCM =
        document.getElementById(
            "enableBCM"
        ).checked;

    const sgwVersion =
        document.getElementById(
            "sgwVersion"
        ).value.trim();

    const bcmVersion =
        document.getElementById(
            "bcmVersion"
        ).value.trim();

    const sgwFile =
        document.getElementById(
            "sgwFirmware"
        ).files[0];

    const bcmFile =
        document.getElementById(
            "bcmFirmware"
        ).files[0];

    if (!campaignId) {

        alert("Enter Campaign ID");

        return;
    }

    if (!vin) {

        alert("Enter VIN");

        return;
    }

    if (!campaignName) {

        alert("Enter Campaign Name");

        return;
    }

    if (!enableSGW && !enableBCM) {

        alert("Select at least one ECU");

        return;
    }

    if (enableSGW) {

        if (!sgwVersion) {

            alert("Enter SGW Target Version");

            return;
        }

        if (!sgwFile) {

            alert("Select SGW Firmware");

            return;
        }
    }

    if (enableBCM) {

        if (!bcmVersion) {

            alert("Enter BCM Target Version");

            return;
        }

        if (!bcmFile) {

            alert("Select BCM Firmware");

            return;
        }
    }

    let sgwFirmware = "";
    let bcmFirmware = "";

    try {

        if (enableSGW) {

            const upload =
                await uploadFirmware(
                    sgwFile
                );

            if (upload.status !== "success") {

                alert("Failed to upload SGW firmware");

                return;
            }

            sgwFirmware = upload.file;
        }

        if (enableBCM) {

            const upload =
                await uploadFirmware(
                    bcmFile
                );

            if (upload.status !== "success") {

                alert("Failed to upload BCM firmware");

                return;
            }

            bcmFirmware = upload.file;
        }

        const params =
            new URLSearchParams();

        params.append(
            "campaign_id",
            campaignId
        );

        params.append(
            "vin",
            vin
        );

        params.append(
            "campaign_name",
            campaignName
        );

        params.append(
            "sgw_target_version",
            enableSGW ? sgwVersion : ""
        );

        params.append(
            "bcm_target_version",
            enableBCM ? bcmVersion : ""
        );

        params.append(
            "sgw_firmware",
            sgwFirmware
        );

        params.append(
            "bcm_firmware",
            bcmFirmware
        );

        const response =
            await fetch(
                SERVER +
                "/campaign?" +
                params.toString(),
                {
                    method: "POST"
                }
            );

        const result =
            await response.json();

        if (
            result.status === "sent"
        ) {

            alert(
                "Campaign Created Successfully"
            );

            window.location =
                "CampaignHistory.html";
        }
        else {

            alert(
                result.message ||
                result.status
            );
        }

    }
    catch (e) {

        alert(
            "Error : " + e
        );

        console.error(e);
    }
}