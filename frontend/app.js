const API_BASE_URL = "https://social-media-downloader-production-19ab.up.railway.app";

document.addEventListener("DOMContentLoaded", () => {
    const extractForm = document.getElementById("extract-form");
    const urlInput = document.getElementById("url-input");
    const btnPaste = document.getElementById("btn-paste");
    const btnExtract = document.getElementById("btn-extract");
    const btnText = document.getElementById("btn-text");
    const btnIcon = document.getElementById("btn-icon");

    const loadingState = document.getElementById("loading-state");
    const resultCard = document.getElementById("result-card");
    const errorCard = document.getElementById("error-card");
    const errorMessage = document.getElementById("error-message");

    const previewThumbnail = document.getElementById("preview-thumbnail");
    const previewDuration = document.getElementById("preview-duration");
    const previewPlatformBadge = document.getElementById("preview-platform-badge");
    const previewTitle = document.getElementById("preview-title");
    const metaPlatform = document.getElementById("meta-platform");
    const metaQuality = document.getElementById("meta-quality");

    const downloadVideoBtn = document.getElementById("download-video-btn");
    const downloadAudioBtn = document.getElementById("download-audio-btn");
    const copyLinkBtn = document.getElementById("copy-link-btn");

    const formatSelect = document.getElementById("format-select");
    const downloadFormatBtn = document.getElementById("download-format-btn");

    // Ad Unlock Modal Elements
    const adUnlockModal = document.getElementById("ad-unlock-modal");
    const closeAdModalBtn = document.getElementById("close-ad-modal-btn");
    const unlockAdBtn = document.getElementById("unlock-ad-btn");
    const adTimerText = document.getElementById("ad-timer-text");
    const unlockBtnIcon = document.getElementById("unlock-btn-icon");

    let currentExtraction = null;
    let isUnlockedForAd = false;
    let pendingDownloadTarget = null;
    let adCountdownInterval = null;

    // Paste from Clipboard
    btnPaste.addEventListener("click", async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                urlInput.value = text.trim();
                showToast("URL pasted from clipboard!", "info");
            }
        } catch (err) {
            showToast("Clipboard access denied or unavailable. Please paste manually.", "warning");
        }
    });

    // Form Submission
    extractForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (!url) return;

        // UI Reset & Loading State
        hide(resultCard);
        hide(errorCard);
        show(loadingState);
        setButtonLoading(true);
        isUnlockedForAd = false;

        try {
            const response = await fetch(`${API_BASE_URL}/api/extract`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || data.detail || "Extraction failed.");
            }

            // Populate Card Data
            currentExtraction = data;
            renderResultCard(data);
            showToast("Media extracted successfully!", "success");

        } catch (err) {
            console.error("Extraction error:", err);
            errorMessage.textContent = err.message || "Failed to extract media. Check the URL and backend server status.";
            show(errorCard);
        } finally {
            hide(loadingState);
            setButtonLoading(false);
        }
    });

    function renderResultCard(data) {
        previewTitle.textContent = data.title || "Social Media Video";
        previewDuration.textContent = data.duration_formatted || "00:00";
        previewThumbnail.src = data.thumbnail || "https://images.unsplash.com/photo-1611162617474-5b21e879e113?q=80&w=600&auto=format&fit=crop";

        const isLongVideo = data.duration > 900 || data.requires_ad_unlock;
        metaPlatform.textContent = `Platform: ${data.platform || 'Social Media'}`;
        metaQuality.textContent = isLongVideo ? "Quality: HD (Ad Lock >15m)" : "Quality: HD";
        previewPlatformBadge.innerHTML = isLongVideo ? 
            `<i class="fa-solid fa-clock text-xs text-amber-300"></i> ${data.platform} (>15m)` : 
            `<i class="fa-solid fa-play text-xs"></i> ${data.platform}`;

        // Direct Video & Audio Buttons
        if (data.video_url) {
            downloadVideoBtn.href = data.video_url;
            downloadVideoBtn.removeAttribute("disabled");
            show(downloadVideoBtn);
        } else {
            hide(downloadVideoBtn);
        }

        if (data.audio_url) {
            downloadAudioBtn.href = data.audio_url;
            show(downloadAudioBtn);
        } else {
            hide(downloadAudioBtn);
        }

        // Formats Select
        formatSelect.innerHTML = "";
        if (data.formats && data.formats.length > 0) {
            data.formats.forEach((fmt) => {
                const opt = document.createElement("option");
                opt.value = fmt.url;
                const sizeInfo = fmt.filesize_approx ? ` (${fmt.filesize_approx})` : "";
                opt.textContent = `[${fmt.ext.toUpperCase()}] ${fmt.resolution}${sizeInfo} - ID: ${fmt.format_id}`;
                formatSelect.appendChild(opt);
            });

            downloadFormatBtn.href = data.formats[0].url;
            show(document.getElementById("format-options-container"));
        } else {
            hide(document.getElementById("format-options-container"));
        }

        show(resultCard);
    }

    // Format Change Listener
    formatSelect.addEventListener("change", (e) => {
        if (e.target.value) {
            downloadFormatBtn.href = e.target.value;
        }
    });

    // Intercept Download Clicks for Long Videos (>15 Mins)
    function handleDownloadGate(e, targetUrl) {
        const isLongVideo = currentExtraction && (currentExtraction.duration > 900 || currentExtraction.requires_ad_unlock);
        if (isLongVideo && !isUnlockedForAd) {
            e.preventDefault();
            pendingDownloadTarget = targetUrl;
            openAdUnlockModal();
        }
    }

    downloadVideoBtn.addEventListener("click", (e) => handleDownloadGate(e, downloadVideoBtn.href));
    downloadAudioBtn.addEventListener("click", (e) => handleDownloadGate(e, downloadAudioBtn.href));
    downloadFormatBtn.addEventListener("click", (e) => handleDownloadGate(e, downloadFormatBtn.href));

    // Ad Unlock Modal Logic
    function openAdUnlockModal() {
        show(adUnlockModal);
        unlockAdBtn.disabled = true;
        unlockAdBtn.className = "w-full py-3.5 rounded-xl bg-slate-800 text-slate-400 text-xs font-bold transition flex items-center justify-center gap-2 cursor-not-allowed";
        unlockBtnIcon.className = "fa-solid fa-lock";

        let secondsLeft = 5;
        adTimerText.textContent = `Watch ad to unlock (${secondsLeft}s)...`;

        if (adCountdownInterval) clearInterval(adCountdownInterval);

        adCountdownInterval = setInterval(() => {
            secondsLeft--;
            if (secondsLeft > 0) {
                adTimerText.textContent = `Watch ad to unlock (${secondsLeft}s)...`;
            } else {
                clearInterval(adCountdownInterval);
                adTimerText.textContent = "🔓 Unlock & Download Now";
                unlockBtnIcon.className = "fa-solid fa-unlock text-emerald-400";
                unlockAdBtn.disabled = false;
                unlockAdBtn.className = "w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/30 transition flex items-center justify-center gap-2 cursor-pointer animate-pulse";
            }
        }, 1000);
    }

    unlockAdBtn.addEventListener("click", () => {
        isUnlockedForAd = true;
        hide(adUnlockModal);
        showToast("Download unlocked after ad view!", "success");

        if (pendingDownloadTarget) {
            window.open(pendingDownloadTarget, "_blank");
            pendingDownloadTarget = null;
        }
    });

    if (closeAdModalBtn) {
        closeAdModalBtn.addEventListener("click", () => {
            if (adCountdownInterval) clearInterval(adCountdownInterval);
            hide(adUnlockModal);
        });
    }

    // Copy Media Link
    copyLinkBtn.addEventListener("click", () => {
        if (currentExtraction && currentExtraction.video_url) {
            navigator.clipboard.writeText(currentExtraction.video_url);
            showToast("Direct media stream link copied to clipboard!", "success");
        }
    });

    // Privacy Policy Modal Handlers
    const privacyModal = document.getElementById("privacy-modal");
    const openPrivacyBtn = document.getElementById("open-privacy-btn");
    const closePrivacyBtn = document.getElementById("close-privacy-btn");
    const dismissPrivacyBtn = document.getElementById("dismiss-privacy-btn");

    if (openPrivacyBtn && privacyModal) {
        openPrivacyBtn.addEventListener("click", () => show(privacyModal));
    }
    if (closePrivacyBtn && privacyModal) {
        closePrivacyBtn.addEventListener("click", () => hide(privacyModal));
    }
    if (dismissPrivacyBtn && privacyModal) {
        dismissPrivacyBtn.addEventListener("click", () => hide(privacyModal));
    }
    if (privacyModal) {
        privacyModal.addEventListener("click", (e) => {
            if (e.target === privacyModal) hide(privacyModal);
        });
    }

    // Helper functions
    function show(el) { if (el) el.classList.remove("hidden"); }
    function hide(el) { if (el) el.classList.add("hidden"); }

    function setButtonLoading(isLoading) {
        if (isLoading) {
            btnExtract.disabled = true;
            btnText.textContent = "Extracting...";
            btnIcon.className = "fa-solid fa-spinner fa-spin";
        } else {
            btnExtract.disabled = false;
            btnText.textContent = "Extract Media";
            btnIcon.className = "fa-solid fa-bolt";
        }
    }

    function showToast(message, type = "info") {
        const toastContainer = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `pointer-events-auto flex items-center gap-2 px-4 py-3 rounded-xl shadow-xl border text-xs font-semibold transform transition-all duration-300 translate-y-2 opacity-0`;

        if (type === "success") {
            toast.classList.add("bg-emerald-950/90", "border-emerald-700", "text-emerald-200");
            toast.innerHTML = `<i class="fa-solid fa-circle-check text-emerald-400"></i> ${message}`;
        } else if (type === "warning") {
            toast.classList.add("bg-amber-950/90", "border-amber-700", "text-amber-200");
            toast.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-amber-400"></i> ${message}`;
        } else {
            toast.classList.add("bg-slate-900/90", "border-slate-700", "text-slate-200");
            toast.innerHTML = `<i class="fa-solid fa-info-circle text-indigo-400"></i> ${message}`;
        }

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.classList.remove("translate-y-2", "opacity-0");
        }, 10);

        setTimeout(() => {
            toast.classList.add("opacity-0", "translate-y-2");
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
});
