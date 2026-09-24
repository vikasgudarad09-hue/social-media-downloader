// Active Backend API service hosted on Render (100% Free, zero external dependency)
const API_BASE_URL = (
    window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
) ? "http://127.0.0.1:8000" : "https://jpmediasaver-api.onrender.com";

document.addEventListener("DOMContentLoaded", () => {
    // Pre-warm Render backend in background so it is instantly awake
    fetch(`${API_BASE_URL}/health`).catch(() => {});

    // --- Jayaprabhu Creations Company Splash Screen ---
    const splashScreen = document.getElementById("company-splash-screen");
    const skipSplashBtn = document.getElementById("skip-splash-btn");

    if (splashScreen) {
        const dismissSplash = () => {
            splashScreen.classList.add("opacity-0", "pointer-events-none");
            setTimeout(() => {
                if (splashScreen && splashScreen.parentNode) {
                    splashScreen.remove();
                }
            }, 750);
        };

        if (skipSplashBtn) {
            skipSplashBtn.addEventListener("click", dismissSplash);
        }

        // Automatic smooth fade-out after exactly 5 seconds
        setTimeout(dismissSplash, 5000);
    }

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

    // Firebase Auth & History UI Elements
    const btnLoginGoogle = document.getElementById("btn-login-google");
    const userProfileBadge = document.getElementById("user-profile-badge");
    const userAvatar = document.getElementById("user-avatar");
    const userName = document.getElementById("user-name");
    const btnSignOut = document.getElementById("btn-sign-out");

    const navHistoryBtn = document.getElementById("nav-history-btn");
    const historyModal = document.getElementById("history-modal");
    const closeHistoryBtn = document.getElementById("close-history-btn");
    const clearHistoryBtn = document.getElementById("clear-history-btn");
    const historyList = document.getElementById("history-list");
    const historyEmptyState = document.getElementById("history-empty-state");
    const historySyncIndicator = document.getElementById("history-sync-indicator");

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

    // Auto-detect platform badge as user types/pastes
    urlInput.addEventListener("input", () => {
        const val = urlInput.value.trim().toLowerCase();

        if (val.includes("youtube.com") || val.includes("youtu.be")) {
            showToast("Detected: YouTube", "info");
        } else if (val.includes("instagram.com") || val.includes("instagr.am")) {
            showToast("Detected: Instagram", "info");
        } else if (val.includes("tiktok.com")) {
            showToast("Detected: TikTok", "info");
        }
    });

    // Form Submission with Auto-Retry
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

        let success = false;
        let data = null;
        let lastErr = null;

        // Fetch Firebase ID Token if logged in
        const headers = {
            "Content-Type": "application/json"
        };
        if (window.JPFirebase && typeof window.JPFirebase.getIdToken === "function") {
            try {
                const token = await window.JPFirebase.getIdToken();
                if (token) {
                    headers["Authorization"] = `Bearer ${token}`;
                }
            } catch (te) {
                console.warn("Could not attach Firebase auth token:", te);
            }
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        try {
            const response = await fetch(`${API_BASE_URL}/api/extract`, {
                method: "POST",
                headers: headers,
                body: JSON.stringify({ url: url }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            const contentType = response.headers.get("content-type") || "";

            if (!response.ok) {
                if (contentType.includes("application/json")) {
                    const errData = await response.json();
                    throw new Error(errData.detail || errData.error || `Server returned error (${response.status})`);
                } else if (response.status === 404) {
                    throw new Error("Backend API is not online or endpoint not found (HTTP 404).");
                } else if (response.status === 502 || response.status === 503) {
                    throw new Error("Backend API server is currently waking up. Please retry in a few seconds.");
                } else {
                    throw new Error(`Server returned HTTP ${response.status}. The backend API may be offline.`);
                }
            }

            if (!contentType.includes("application/json")) {
                throw new Error("Backend returned an unexpected response format.");
            }

            data = await response.json();

            if (data.success) {
                success = true;
            } else {
                lastErr = new Error(data.error || data.detail || "Extraction failed.");
            }
        } catch (err) {
            clearTimeout(timeoutId);
            if (err.name === 'AbortError') {
                lastErr = new Error("Request timed out. The server was busy waking up; please click Extract again.");
            } else {
                lastErr = err;
            }
        }

        try {
            if (!success || !data) {
                throw lastErr || new Error("Failed to extract media after retry.");
            }

            // Populate Card Data
            currentExtraction = data;
            renderResultCard(data);
            showToast("Media extracted successfully!", "success");

            // Automatically record in Firebase Firestore / Local History
            if (window.JPFirebase && typeof window.JPFirebase.saveDownload === "function") {
                window.JPFirebase.saveDownload(data).catch(e => console.warn("Auto-save history notice:", e));
            }

        } catch (err) {
            console.error("Extraction error:", err);
            errorMessage.textContent = err.message || "Failed to extract media. Please check the URL and try again.";
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

        metaPlatform.textContent = `Platform: ${data.platform || 'Social Media'}`;
        metaQuality.textContent = "Quality: HD";
        previewPlatformBadge.innerHTML = `<i class="fa-solid fa-play text-xs"></i> ${data.platform || 'Media'}`;

        const safeTitle = (data.title || "video").replace(/[^\w\s.-]/g, "_").substring(0, 50);

        // Direct Video & Audio Buttons (via proxy-download for forced direct file save)
        if (data.video_url) {
            downloadVideoBtn.href = `${API_BASE_URL}/api/proxy-download?url=${encodeURIComponent(data.video_url)}&filename=${encodeURIComponent(safeTitle + '.mp4')}`;
            downloadVideoBtn.removeAttribute("disabled");
            show(downloadVideoBtn);
        } else {
            hide(downloadVideoBtn);
        }

        if (data.audio_url) {
            downloadAudioBtn.href = `${API_BASE_URL}/api/proxy-download?url=${encodeURIComponent(data.audio_url)}&filename=${encodeURIComponent(safeTitle + '.mp3')}`;
            show(downloadAudioBtn);
        } else {
            hide(downloadAudioBtn);
        }

        // Formats Select
        formatSelect.innerHTML = "";
        if (data.formats && data.formats.length > 0) {
            data.formats.forEach((fmt) => {
                const opt = document.createElement("option");
                opt.value = `${API_BASE_URL}/api/proxy-download?url=${encodeURIComponent(fmt.url)}&filename=${encodeURIComponent(safeTitle + '_' + fmt.resolution + '.' + fmt.ext)}`;
                const sizeInfo = fmt.filesize_approx ? ` (${fmt.filesize_approx})` : "";
                opt.textContent = `[${fmt.ext.toUpperCase()}] ${fmt.resolution}${sizeInfo} - ID: ${fmt.format_id}`;
                formatSelect.appendChild(opt);
            });

            downloadFormatBtn.href = formatSelect.options[0].value;
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

    // Direct Instant Downloads (Zero Ad Interruption)
    // Buttons naturally trigger direct file streaming without modal gates

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

    // --- Firebase Authentication Handling ---
    if (btnLoginGoogle) {
        btnLoginGoogle.addEventListener("click", async () => {
            try {
                showToast("Signing in...", "info");
                if (window.JPFirebase && typeof window.JPFirebase.signInWithGoogle === "function") {
                    await window.JPFirebase.signInWithGoogle();
                    showToast("Signed in successfully!", "success");
                }
            } catch (err) {
                console.error("Login failed:", err);
                showToast(err.message || "Failed to sign in. Please try again.", "warning");
            }
        });
    }

    if (btnSignOut) {
        btnSignOut.addEventListener("click", async () => {
            try {
                if (window.JPFirebase && typeof window.JPFirebase.signOut === "function") {
                    await window.JPFirebase.signOut();
                    showToast("Signed out successfully.", "info");
                }
            } catch (err) {
                console.error("Sign out error:", err);
            }
        });
    }

    // Subscribe to Auth state changes
    if (window.JPFirebase && typeof window.JPFirebase.onAuthStateChanged === "function") {
        window.JPFirebase.onAuthStateChanged((user) => {
            if (user) {
                hide(btnLoginGoogle);
                show(userProfileBadge);
                userProfileBadge.classList.add("flex");
                userName.textContent = user.displayName || user.email || "Guest";
                userAvatar.src = user.photoURL || "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&auto=format&fit=crop&q=80";
                if (historySyncIndicator) {
                    historySyncIndicator.textContent = (window.JPFirebase && window.JPFirebase.isConfigured) ? 
                        `Synced to Firebase Cloud (${user.email || 'Guest'})` : 
                        "Saved Locally (Standby Mode)";
                }
            } else {
                show(btnLoginGoogle);
                hide(userProfileBadge);
                userProfileBadge.classList.remove("flex");
                if (historySyncIndicator) {
                    historySyncIndicator.textContent = "Synced via Firebase & Local Storage";
                }
            }
        });
    }

    // --- User Download History Modal Handling ---
    if (navHistoryBtn && historyModal) {
        navHistoryBtn.addEventListener("click", async () => {
            show(historyModal);
            await renderHistoryModal();
        });
    }

    if (closeHistoryBtn && historyModal) {
        closeHistoryBtn.addEventListener("click", () => hide(historyModal));
    }

    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener("click", async () => {
            if (confirm("Are you sure you want to clear your download history?")) {
                if (window.JPFirebase && typeof window.JPFirebase.clearDownloads === "function") {
                    await window.JPFirebase.clearDownloads();
                    await renderHistoryModal();
                    showToast("Download history cleared.", "info");
                }
            }
        });
    }

    if (historyModal) {
        historyModal.addEventListener("click", (e) => {
            if (e.target === historyModal) hide(historyModal);
        });
    }

    async function renderHistoryModal() {
        if (!historyList) return;
        historyList.innerHTML = '<div class="py-6 text-center text-slate-400 text-xs"><i class="fa-solid fa-spinner fa-spin mr-2"></i> Loading history...</div>';
        hide(historyEmptyState);

        let items = [];
        if (window.JPFirebase && typeof window.JPFirebase.loadDownloads === "function") {
            try {
                items = await window.JPFirebase.loadDownloads();
            } catch (err) {
                console.error("Failed to load history:", err);
            }
        }

        historyList.innerHTML = "";

        if (!items || items.length === 0) {
            show(historyEmptyState);
            return;
        }

        hide(historyEmptyState);

        items.forEach((item) => {
            const row = document.createElement("div");
            row.className = "flex items-center gap-3 py-3 first:pt-0 last:pb-0 hover:bg-slate-800/30 p-2 rounded-xl transition";
            
            const thumbSrc = item.thumbnail || "https://images.unsplash.com/photo-1611162617474-5b21e879e113?q=80&w=200&auto=format&fit=crop";
            const dateStr = item.timestamp ? new Date(item.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : "Recent";

            row.innerHTML = `
                <img src="${thumbSrc}" alt="Thumbnail" class="w-16 h-12 rounded-lg object-cover bg-slate-950 flex-shrink-0 border border-slate-800">
                <div class="flex-1 min-w-0">
                    <h4 class="text-xs font-semibold text-slate-100 truncate">${item.title || "Video"}</h4>
                    <div class="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                        <span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">${item.platform || "Media"}</span>
                        <span>${item.duration_formatted || "00:00"}</span>
                        <span>• ${dateStr}</span>
                    </div>
                </div>
                <div class="flex items-center gap-1.5 flex-shrink-0">
                    <button type="button" class="btn-history-extract px-2.5 py-1.5 rounded-lg bg-indigo-600/80 hover:bg-indigo-600 text-white text-xs font-semibold transition flex items-center gap-1 cursor-pointer" title="Extract Again">
                        <i class="fa-solid fa-arrows-rotate text-[10px]"></i>
                        <span class="hidden sm:inline">Extract</span>
                    </button>
                    <button type="button" class="btn-history-copy p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs transition cursor-pointer" title="Copy Link">
                        <i class="fa-regular fa-copy"></i>
                    </button>
                </div>
            `;

            // Wire Extract button to re-fill URL and click extract
            const extractBtn = row.querySelector(".btn-history-extract");
            if (extractBtn && item.url) {
                extractBtn.addEventListener("click", () => {
                    hide(historyModal);
                    urlInput.value = item.url;
                    urlInput.scrollIntoView({ behavior: "smooth" });
                    btnExtract.click();
                });
            }

            // Wire Copy button
            const copyBtn = row.querySelector(".btn-history-copy");
            if (copyBtn && item.url) {
                copyBtn.addEventListener("click", () => {
                    navigator.clipboard.writeText(item.url);
                    showToast("Video link copied to clipboard!", "success");
                });
            }

            historyList.appendChild(row);
        });
    }

    // --- Support & Donation (UPI & PayPal) Modal Handling ---
    const supportModal = document.getElementById("support-modal");
    const closeSupportBtn = document.getElementById("close-support-btn");
    const navSupportBtn = document.getElementById("nav-support-btn");
    const footerSupportBtn = document.getElementById("footer-support-btn");
    const triggerSupportUpiBtns = document.querySelectorAll(".btn-open-support-modal-upi");
    const triggerSupportPaypalBtns = document.querySelectorAll(".btn-open-support-modal-paypal");

    const tabBtnUpi = document.getElementById("tab-btn-upi");
    const tabBtnPaypal = document.getElementById("tab-btn-paypal");
    const tabContentUpi = document.getElementById("tab-content-upi");
    const tabContentPaypal = document.getElementById("tab-content-paypal");

    const displayUpiId = document.getElementById("display-upi-id");
    const copyUpiBtn = document.getElementById("copy-upi-btn");
    const upiQrImage = document.getElementById("upi-qr-image");
    const directUpiLink = document.getElementById("direct-upi-link");
    const directUpiText = document.getElementById("direct-upi-text");
    const customUpiAmountInput = document.getElementById("custom-upi-amount");
    const upiAmountPills = document.querySelectorAll("#upi-amount-pills .upi-pill");

    const directPaypalBtn = document.getElementById("direct-paypal-btn");
    const directPaypalText = document.getElementById("direct-paypal-text");
    const copyPaypalBtn = document.getElementById("copy-paypal-btn");
    const displayPaypalEmail = document.getElementById("display-paypal-email");
    const customPaypalAmountInput = document.getElementById("custom-paypal-amount");
    const paypalAmountPills = document.querySelectorAll("#paypal-amount-pills .paypal-pill");

    // Get active config or fallback
    const payConfig = window.JPPaymentConfig || {
        upiId: "vickyunion99@ibl",
        upiPayeeName: "VIKAS PRABHU GUDARAD",
        paypalEmail: "gudaradvikas09@gmail.com",
        paypalUrl: "https://www.paypal.com/donate?business=gudaradvikas09@gmail.com&no_recurring=0&currency_code=USD"
    };

    let selectedUpiAmount = 100;
    let selectedPaypalAmount = 5;

    function updateUpiDetails(amount) {
        selectedUpiAmount = amount;
        const formattedAmount = (typeof amount === "number" ? amount : parseFloat(amount) || 1).toFixed(2);
        const payeeEncoded = encodeURIComponent(payConfig.upiPayeeName || "VIKAS PRABHU GUDARAD");
        const upiUri = `upi://pay?pa=${encodeURIComponent(payConfig.upiId)}&pn=${payeeEncoded}&am=${formattedAmount}&cu=INR&tn=Support%20Jayaprabhu%20Creations`;
        
        if (directUpiLink) {
            directUpiLink.href = upiUri;
        }
        if (directUpiText) {
            directUpiText.textContent = `Open in PhonePe / GPay / Paytm (₹${amount})`;
        }
        if (displayUpiId) {
            displayUpiId.textContent = payConfig.upiId;
        }
        const qrAmountBadge = document.getElementById("qr-amount-badge");
        if (qrAmountBadge) {
            qrAmountBadge.textContent = `₹${amount}`;
        }
    }

    // Direct UPI Link Click Handler (Smart PC vs Mobile handling)
    if (directUpiLink) {
        directUpiLink.addEventListener("click", (e) => {
            const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
            if (!isMobile) {
                // On PC / Laptop, prevent dead link since Windows has no UPI app
                e.preventDefault();
                navigator.clipboard.writeText(payConfig.upiId);

                // Highlight the QR code container visually
                const qrContainer = document.getElementById("upi-qr-container");
                if (qrContainer) {
                    qrContainer.classList.add("ring-4", "ring-purple-400", "scale-105");
                    setTimeout(() => {
                        qrContainer.classList.remove("ring-4", "ring-purple-400", "scale-105");
                    }, 1200);
                }

                showToast(`📲 UPI apps only open on mobile phones! On PC/Laptop, please scan the QR code above with your phone camera, PhonePe, or GPay. (UPI ID copied!)`, "info", 6500);
            } else {
                // On Mobile, navigate to trigger app chooser
                window.location.href = directUpiLink.href;
            }
        });
    }

    function updatePaypalDetails(amount) {
        selectedPaypalAmount = amount;
        if (directPaypalBtn) {
            directPaypalBtn.href = `https://www.paypal.com/donate?business=${encodeURIComponent(payConfig.paypalEmail)}&amount=${amount}&currency_code=USD`;
        }
        if (directPaypalText) {
            directPaypalText.textContent = `Pay $${amount} with PayPal`;
        }
        if (displayPaypalEmail && payConfig.paypalEmail) {
            displayPaypalEmail.textContent = payConfig.paypalEmail;
        }
    }

    // Initial config apply
    updateUpiDetails(100);
    updatePaypalDetails(5);

    // Custom Amount Input Listeners
    if (customUpiAmountInput) {
        customUpiAmountInput.addEventListener("input", (e) => {
            const raw = parseFloat(e.target.value);
            const val = (!isNaN(raw) && raw > 0) ? raw : 1;
            
            upiAmountPills.forEach(p => {
                if (parseInt(p.dataset.amount, 10) === val) {
                    p.classList.add("active", "border-purple-500", "bg-purple-600/20", "text-purple-300", "font-bold");
                    p.classList.remove("border-slate-700", "bg-slate-900", "text-slate-300");
                } else {
                    p.classList.remove("active", "border-purple-500", "bg-purple-600/20", "text-purple-300", "font-bold");
                    p.classList.add("border-slate-700", "bg-slate-900", "text-slate-300");
                }
            });

            updateUpiDetails(val);
        });
    }

    if (customPaypalAmountInput) {
        customPaypalAmountInput.addEventListener("input", (e) => {
            const raw = parseFloat(e.target.value);
            const val = (!isNaN(raw) && raw > 0) ? raw : 1;

            paypalAmountPills.forEach(p => {
                if (parseInt(p.dataset.amount, 10) === val) {
                    p.classList.add("active", "border-sky-500", "bg-sky-600/20", "text-sky-300", "font-bold");
                    p.classList.remove("border-slate-700", "bg-slate-900", "text-slate-300");
                } else {
                    p.classList.remove("active", "border-sky-500", "bg-sky-600/20", "text-sky-300", "font-bold");
                    p.classList.add("border-slate-700", "bg-slate-900", "text-slate-300");
                }
            });

            updatePaypalDetails(val);
        });
    }

    function switchSupportTab(tab) {
        if (tab === "upi") {
            show(tabContentUpi);
            hide(tabContentPaypal);
            if (tabBtnUpi) tabBtnUpi.className = "py-2.5 rounded-lg transition flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow cursor-pointer";
            if (tabBtnPaypal) tabBtnPaypal.className = "py-2.5 rounded-lg transition flex items-center justify-center gap-2 text-slate-400 hover:text-slate-200 cursor-pointer";
        } else {
            hide(tabContentUpi);
            show(tabContentPaypal);
            if (tabBtnPaypal) tabBtnPaypal.className = "py-2.5 rounded-lg transition flex items-center justify-center gap-2 bg-gradient-to-r from-sky-600 to-blue-600 text-white shadow cursor-pointer";
            if (tabBtnUpi) tabBtnUpi.className = "py-2.5 rounded-lg transition flex items-center justify-center gap-2 text-slate-400 hover:text-slate-200 cursor-pointer";
        }
    }

    if (tabBtnUpi) tabBtnUpi.addEventListener("click", () => switchSupportTab("upi"));
    if (tabBtnPaypal) tabBtnPaypal.addEventListener("click", () => switchSupportTab("paypal"));

    function openSupportModal(defaultTab = "upi") {
        switchSupportTab(defaultTab);
        show(supportModal);
    }

    if (navSupportBtn) navSupportBtn.addEventListener("click", () => openSupportModal("upi"));
    if (footerSupportBtn) footerSupportBtn.addEventListener("click", () => openSupportModal("upi"));

    triggerSupportUpiBtns.forEach(btn => {
        btn.addEventListener("click", () => openSupportModal("upi"));
    });
    triggerSupportPaypalBtns.forEach(btn => {
        btn.addEventListener("click", () => openSupportModal("paypal"));
    });

    if (closeSupportBtn && supportModal) {
        closeSupportBtn.addEventListener("click", () => hide(supportModal));
    }
    if (supportModal) {
        supportModal.addEventListener("click", (e) => {
            if (e.target === supportModal) hide(supportModal);
        });
    }

    // Copy UPI ID button
    if (copyUpiBtn) {
        copyUpiBtn.addEventListener("click", () => {
            navigator.clipboard.writeText(payConfig.upiId);
            showToast(`UPI ID (${payConfig.upiId}) copied to clipboard!`, "success");
        });
    }

    // Copy PayPal email button
    if (copyPaypalBtn) {
        copyPaypalBtn.addEventListener("click", () => {
            navigator.clipboard.writeText(payConfig.paypalEmail);
            showToast(`PayPal email (${payConfig.paypalEmail}) copied to clipboard!`, "success");
        });
    }

    // UPI Amount Pill clicks
    upiAmountPills.forEach(pill => {
        pill.addEventListener("click", () => {
            upiAmountPills.forEach(p => {
                p.classList.remove("active", "border-purple-500", "bg-purple-600/20", "text-purple-300", "font-bold");
                p.classList.add("border-slate-700", "bg-slate-900", "text-slate-300");
            });
            pill.classList.add("active", "border-purple-500", "bg-purple-600/20", "text-purple-300", "font-bold");
            pill.classList.remove("border-slate-700", "bg-slate-900", "text-slate-300");

            const amt = parseInt(pill.dataset.amount, 10) || 100;
            if (customUpiAmountInput) {
                customUpiAmountInput.value = amt;
            }
            updateUpiDetails(amt);
        });
    });

    // PayPal Amount Pill clicks
    paypalAmountPills.forEach(pill => {
        pill.addEventListener("click", () => {
            paypalAmountPills.forEach(p => {
                p.classList.remove("active", "border-sky-500", "bg-sky-600/20", "text-sky-300", "font-bold");
                p.classList.add("border-slate-700", "bg-slate-900", "text-slate-300");
            });
            pill.classList.add("active", "border-sky-500", "bg-sky-600/20", "text-sky-300", "font-bold");
            pill.classList.remove("border-slate-700", "bg-slate-900", "text-slate-300");

            const amt = parseInt(pill.dataset.amount, 10) || 5;
            if (customPaypalAmountInput) {
                customPaypalAmountInput.value = amt;
            }
            updatePaypalDetails(amt);
        });
    });

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
