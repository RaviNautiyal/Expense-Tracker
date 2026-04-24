const VIDEO_URL = "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1";
const modal = document.getElementById("video-modal");
const videoFrame = document.getElementById("video-frame");

function openVideoModal() {
    if (!modal || !videoFrame) {
        return;
    }

    videoFrame.src = VIDEO_URL;
    modal.classList.add("active");
    document.body.style.overflow = "hidden";
}

function closeVideoModal() {
    if (!modal || !videoFrame) {
        return;
    }

    videoFrame.src = "";
    modal.classList.remove("active");
    document.body.style.overflow = "";
}

if (modal) {
    modal.addEventListener("click", function (event) {
        if (event.target === modal) {
            closeVideoModal();
        }
    });
}

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && modal && modal.classList.contains("active")) {
        closeVideoModal();
    }
});
