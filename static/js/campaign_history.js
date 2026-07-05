const SERVER = "https://fota-demo.onrender.com";

async function loadCampaigns() {

    try {

        const response =
            await fetch(
                SERVER + "/campaigns",
                {
                    cache: "no-store"
                }
            );

        const campaigns =
            await response.json();

        const tbody =
            document.getElementById(
                "campaignList"
            );

        tbody.innerHTML = "";

        const search =
            document.getElementById(
                "searchCampaign"
            ).value
            .toLowerCase();

        campaigns.forEach(c => {

            if (
                search &&
                !c.campaign_id
                    .toLowerCase()
                    .includes(search) &&
                !c.vin
                    .toLowerCase()
                    .includes(search)
            ) {
                return;
            }

            let sgw = "-";
            let bcm = "-";

            if (
                c.target_ecu == "SGW"
            ) {

                sgw =
                    c.sgw_target_version;

            }
            else if (
                c.target_ecu == "BCM"
            ) {

                bcm =
                    c.bcm_target_version;

            }
            else {

                sgw =
                    c.sgw_target_version;

                bcm =
                    c.bcm_target_version;
            }

            tbody.innerHTML += `

<tr>

<td>${c.campaign_id}</td>

<td>${c.campaign_name}</td>

<td>${c.vin}</td>

<td>${c.target_ecu}</td>

<td>${sgw}</td>

<td>${bcm}</td>

<td>

<span class="statusBadge">

${c.status}

</span>

</td>

<td>

<button
class="deleteBtn"
onclick="deleteCampaign('${c.campaign_id}')">

Delete

</button>

</td>

</tr>

`;

        });

    }
    catch (e) {

        console.error(e);

        alert(
            "Unable to load campaigns."
        );

    }

}

async function deleteCampaign(id) {

    if (
        !confirm(
            "Delete Campaign " +
            id +
            " ?"
        )
    ) {
        return;
    }

    try {

        const response =
            await fetch(

                SERVER +
                "/campaign/" +
                id,

                {
                    method: "DELETE"
                }

            );

        const result =
            await response.json();

        if (
            result.status ==
            "deleted"
        ) {

            loadCampaigns();

        }
        else {

            alert(
                "Delete failed"
            );

        }

    }
    catch (e) {

        alert(e);

    }

}

document
.getElementById(
    "searchCampaign"
)
.addEventListener(

    "input",

    loadCampaigns

);

loadCampaigns();

setInterval(

    loadCampaigns,

    3000

);