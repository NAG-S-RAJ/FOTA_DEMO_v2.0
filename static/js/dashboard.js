const SERVER =
"https://fota-demo.onrender.com";

function downloadLogs(){

    window.location =
        SERVER + "/download_logs";
}

async function deleteCampaign(id){

    if(!confirm(
        "Delete this campaign?"
    )){
        return;
    }

    await fetch(
        SERVER +
        "/campaign/" +
        id,
        {
            method:"DELETE"
        }
    );

    loadCampaigns();
}

/* ==========================
   PENDING TBMS
========================== */

async function loadPending(){

    const response =
    await fetch(
        SERVER + "/pending"
    );

    const data =
    await response.json();

    document.getElementById(
    "pendingCount"
    ).innerText =
    data.pending.length;

    const div =
    document.getElementById(
        "pendingList"
    );

    div.innerHTML = "";

    if(data.pending.length === 0){

        div.innerHTML =
        "No Pending Requests";

        return;
    }

    data.pending.forEach(vin=>{

        div.innerHTML +=
        `
        <div class="pendingItem">

            <b>${vin}</b>

            <br><br>

            <button
            class="approve"
            onclick="approveTBM('${vin}')">

            Approve

            </button>

            <button
            class="reject"
            onclick="rejectTBM('${vin}')">

            Reject

            </button>

        </div>
        `;
    });
}


/* ==========================
   CONNECTED TBMS
========================== */

async function loadTBMs(){

    const response =
    await fetch(
        SERVER + "/tbms"
    );

    const data =
    await response.json();

    document.getElementById(
    "onlineCount"
    ).innerText =
    data.online_tbms.length;

    const div =
    document.getElementById(
        "tbmList"
    );

    div.innerHTML = "";

    if(data.online_tbms.length === 0){

        div.innerHTML =
        "No Connected TBMs";

        return;
    }

    data.online_tbms.forEach(vin=>{

        div.innerHTML +=
        `
        <div class="onlineItem">

            VIN : ${vin}

        </div>
        `;
    });
}


/* ==========================
   APPROVE TBM
========================== */

async function approveTBM(vin){

    await fetch(
        SERVER +
        "/approve/" +
        vin,
        {
            method:"POST"
        }
    );

    loadPending();
    loadTBMs();
}


/* ==========================
   REJECT TBM
========================== */

async function rejectTBM(vin){

    await fetch(
        SERVER +
        "/reject/" +
        vin,
        {
            method:"POST"
        }
    );

    loadPending();
}


/* ==========================
   CREATE CAMPAIGN
========================== */

async function createCampaign(){

    const campaignId =
    document.getElementById(
        "campaignId"
    ).value.trim();
    
    const vin =
    document.getElementById(
        "vin"
    ).value;

    const campaign =
    document.getElementById(
        "campaignName"
    ).value;

    const file =
    document.getElementById(
        "campaignFirmware"
    ).files[0];

    if(
        !campaignId ||
        !vin ||
        !campaign ||
        !file
    ){

        alert(
            "Fill all fields"
        );

        return;
    }

    try{

        // -------------------------
        // Upload Firmware
        // -------------------------

        const formData =
        new FormData();

        formData.append(
            "file",
            file
        );

        const uploadResponse =
        await fetch(
            SERVER + "/upload",
            {
                method:"POST",
                body:formData
            }
        );

        const uploadResult =
        await uploadResponse.json();

        const firmwareFile =
        uploadResult.file;

        // -------------------------
        // Create Campaign
        // -------------------------

        const campaignUrl =
            SERVER +
            "/campaign" +
            "?campaign_id=" +
            encodeURIComponent(campaignId) +
            "&vin=" +
            encodeURIComponent(vin) +
            "&campaign_name=" +
            encodeURIComponent(campaign) +
            "&firmware_file=" +
            encodeURIComponent(
                firmwareFile
        );

        const response =
        await fetch(
            campaignUrl,
            {
                method:"POST"
            }
        );

        const result =
        await response.json();

        alert(
            JSON.stringify(
                result
            )
        );

        loadCampaigns();

    }
    catch(error){

        alert(
            "Campaign Creation Failed"
        );

        console.error(error);
    }
}


/* ==========================
   CAMPAIGNS
========================== */

async function loadCampaigns(){

    const response =
    await fetch(
        SERVER + "/campaigns"
    );

    const campaigns =
    await response.json();

    document.getElementById(
    "campaignCount"
    ).innerText =
    campaigns.length;

    const div =
    document.getElementById(
        "campaignList"
    );

    div.innerHTML = "";

    if(campaigns.length === 0){

        div.innerHTML =
        "No Campaigns";

        return;
    }

    campaigns.forEach(c=>{

        div.innerHTML += `
        <div class="campaignItem">
        
            <div style="
                display:flex;
                justify-content:space-between;
                align-items:flex-start;
            ">
        
                <div>
                
                    <b>${c.campaign_name}</b><br>

                    Campaign ID : ${c.campaign_id}<br>
                                    
                    VIN : ${c.vin}<br>
                                    
                    Firmware : ${c.firmware_file}<br>
                                    
                    Status : ${c.status}
                
                </div>
            
                <button
                    class="deleteBtn"
                    onclick="deleteCampaign('${c.campaign_id}')">
            
                    Delete
            
                </button>
            
            </div>
        
        </div>
        `;
    });
}


/* ==========================
   LOGS
========================== */

async function loadLogs(){

    const response =
    await fetch(
        SERVER + "/logs"
    );

    const data =
    await response.json();

    const logs =
    document.getElementById(
        "logs"
    );

    logs.innerHTML = "";

    data.forEach(item=>{

        logs.innerHTML +=
        item +
        "<br>";

    });

    logs.scrollTop =
    logs.scrollHeight;
}


/* ==========================
   AUTO REFRESH
========================== */

loadPending();
loadTBMs();
loadLogs();
loadCampaigns();

setInterval(
    loadPending,
    1000
);

setInterval(
    loadTBMs,
    2000
);

setInterval(
    loadLogs,
    1000
);

setInterval(
    loadCampaigns,
    3000
);