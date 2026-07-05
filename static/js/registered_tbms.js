const SERVER = "https://fota-demo.onrender.com";

let tbms = [];
let onlineTBMs = [];

async function loadTBMs() {

    try {

        const tbmResponse =
            await fetch(
                SERVER + "/registered_tbms",
                {
                    cache: "no-store"
                }
            );

        tbms =
            await tbmResponse.json();

        const onlineResponse =
            await fetch(
                SERVER + "/tbms",
                {
                    cache: "no-store"
                }
            );

        const online =
            await onlineResponse.json();

        onlineTBMs =
            online.online_tbms;

        renderTable();

    }
    catch(e){

        console.error(e);

    }

}

function renderTable(){

    const tbody =
        document.getElementById(
            "tbmList"
        );

    tbody.innerHTML = "";

    const search =
        document
        .getElementById(
            "searchVIN"
        )
        .value
        .toLowerCase();

    tbms.forEach(tbm=>{

        if(
            search &&
            !tbm.vin
            .toLowerCase()
            .includes(search)
        ){
            return;
        }

        const online =
            onlineTBMs.includes(
                tbm.vin
            );

        tbody.innerHTML += `

<tr>

<td>${tbm.vin}</td>

<td>

<span class="${
online?
'statusOnline':
'statusOffline'
}">

${
online?
'ONLINE':
'OFFLINE'
}

</span>

</td>

<td>

${tbm.sgw_version}

</td>

<td>

${tbm.bcm_version}

</td>

<td>

${new Date(
tbm.added_on
).toLocaleString()}

</td>

<td>

<button
class="deleteBtn"
onclick="deleteTBM('${tbm.vin}')">

Delete

</button>

</td>

</tr>

`;

    });

    document.getElementById(
        "registeredCount"
    ).innerText =
        tbms.length;

    document.getElementById(
        "onlineCount"
    ).innerText =
        onlineTBMs.length;

    if(tbms.length){

        document.getElementById(
            "latestVersion"
        ).innerText =
        tbms[0].sgw_version +
        " / " +
        tbms[0].bcm_version;

    }else{

        document.getElementById(
            "latestVersion"
        ).innerText="--";

    }

}

async function addTBM(){

    const vin =
        document
        .getElementById(
            "vin"
        )
        .value
        .trim();

    const sgw =
        document
        .getElementById(
            "sgwVersion"
        )
        .value
        .trim();

    const bcm =
        document
        .getElementById(
            "bcmVersion"
        )
        .value
        .trim();

    if(!vin){

        alert("Enter VIN");

        return;
    }

    if(!sgw){

        alert("Enter SGW Version");

        return;
    }

    if(!bcm){

        alert("Enter BCM Version");

        return;
    }

    const params =
        new URLSearchParams();

    params.append(
        "vin",
        vin
    );

    params.append(
        "sgw_version",
        sgw
    );

    params.append(
        "bcm_version",
        bcm
    );

    const response =
        await fetch(

            SERVER +
            "/register_tbm?" +
            params.toString(),

            {
                method:"POST"
            }

        );

    const result =
        await response.json();

    if(result.status=="success"){

        alert(
            "TBM Registered"
        );

        loadTBMs();

    }else{

        alert(
            result.status
        );

    }

}

async function deleteTBM(vin){

    if(
        !confirm(
            "Delete "+vin+" ?"
        )
    ){
        return;
    }

    await fetch(

        SERVER+
        "/registered_tbm/"+vin,

        {
            method:"DELETE"
        }

    );

    loadTBMs();

}

function filterTBMs(){

    renderTable();

}

loadTBMs();

setInterval(

    loadTBMs,

    3000

);