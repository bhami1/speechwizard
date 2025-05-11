// File: static/js/sidebar.js
// This is a new file to be created

function openSidebar() {
    document.getElementById("transcription-sidebar").style.width = "300px";
    document.getElementById("overlay").style.display = "block";
}

function closeSidebar() {
    document.getElementById("transcription-sidebar").style.width = "0";
    document.getElementById("overlay").style.display = "none";
}

function copyText(text) {
    navigator.clipboard.writeText(text)
        .then(() => {
            alert("Text copied to clipboard!");
        })
        .catch(err => {
            console.error("Failed to copy text: ", err);
        });
}