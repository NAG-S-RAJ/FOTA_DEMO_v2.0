if(
    sessionStorage.getItem(
        "fota_logged_in"
    ) !== "true"
){
    window.location = "login.html";
}

function logout(){

    sessionStorage.removeItem(
        "fota_logged_in"
    );

    window.location =
        "login.html";
}