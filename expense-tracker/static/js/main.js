// main.js — students will add JavaScript here as features are built

// Video Modal Functionality
const VIDEO_URL = "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1"; // Placeholder video
const modal = document.getElementById('video-modal');
const videoFrame = document.getElementById('video-frame');

function openVideoModal() {
    if (modal) {
        videoFrame.src = VIDEO_URL;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeVideoModal() {
    if (modal) {
        videoFrame.src = '';
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Close modal when clicking outside content
if (modal) {
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeVideoModal();
        }
    });
}

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && modal && modal.classList.contains('active')) {
        closeVideoModal();
    }
});
