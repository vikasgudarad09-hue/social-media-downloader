(function () {
    'use me strict';

    const BUTTON_ID = "wa-media-extractor-btn";
    const TOAST_ID = "wa-media-extractor-toast";

    console.log("[WhatsApp Extractor] Extension content script loaded.");

    // Initialize observer to detect WhatsApp Web DOM changes
    const observer = new MutationObserver(() => {
        injectDownloadButton();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Try immediate injection
    injectDownloadButton();

    function injectDownloadButton() {
        if (document.getElementById(BUTTON_ID)) return; // Already injected

        // Look for WhatsApp Web header element
        const headerSelectors = [
            '#main header',
            'header._amie',
            'header',
            '[data-tab="2"] header'
        ];

        let header = null;
        for (const selector of headerSelectors) {
            header = document.querySelector(selector);
            if (header) break;
        }

        if (!header) return;

        // Create WhatsApp themed Download Button
        const btnContainer = document.createElement("div");
        btnContainer.id = BUTTON_ID;
        btnContainer.style.cssText = `
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-left: auto;
            margin-right: 12px;
            padding: 6px 14px;
            background: linear-gradient(135deg, #25D366, #128C7E);
            color: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 13px;
            font-weight: 600;
            border-radius: 20px;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(37, 211, 102, 0.3);
            transition: all 0.2s ease;
            user-select: none;
            z-index: 9999;
        `;

        btnContainer.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y3="3"></line>
            </svg>
            <span>Download All Media</span>
        `;

        btnContainer.addEventListener("mouseenter", () => {
            btnContainer.style.transform = "scale(1.04)";
            btnContainer.style.boxShadow = "0 4px 12px rgba(37, 211, 102, 0.4)";
        });

        btnContainer.addEventListener("mouseleave", () => {
            btnContainer.style.transform = "scale(1)";
            btnContainer.style.boxShadow = "0 2px 8px rgba(37, 211, 102, 0.3)";
        });

        btnContainer.addEventListener("click", scanAndDownloadMedia);

        header.appendChild(btnContainer);
        console.log("[WhatsApp Extractor] 'Download All Media' button successfully injected!");
    }

    function scanAndDownloadMedia() {
        console.log("[WhatsApp Extractor] Scanning DOM chat history for blob media...");

        // Container selector for active chat panel
        const chatContainer = document.querySelector("#main") || document.body;

        const mediaList = [];
        const seenUrls = new Set();

        // 1. Scan images
        const images = chatContainer.querySelectorAll("img");
        images.forEach(img => {
            const src = img.src || img.getAttribute("src");
            if (src && (src.startsWith("blob:") || src.includes("whatsapp"))) {
                // Ignore small avatar icons or emojis (< 60px)
                if (img.naturalWidth > 60 || img.naturalHeight > 60 || img.width > 60 || src.startsWith("blob:")) {
                    if (!seenUrls.has(src)) {
                        seenUrls.add(src);
                        mediaList.push({
                            type: "image",
                            url: src,
                            ext: "jpg"
                        });
                    }
                }
            }
        });

        // 2. Scan videos & video sources
        const videos = chatContainer.querySelectorAll("video");
        videos.forEach(video => {
            let src = video.src || video.getAttribute("src");
            if (!src) {
                const source = video.querySelector("source");
                if (source) src = source.src || source.getAttribute("src");
            }

            if (src && (src.startsWith("blob:") || src.includes("whatsapp"))) {
                if (!seenUrls.has(src)) {
                    seenUrls.add(src);
                    mediaList.push({
                        type: "video",
                        url: src,
                        ext: "mp4"
                    });
                }
            }
        });

        if (mediaList.length === 0) {
            showToast("No blob media (images or videos) found in current chat history.", "warning");
            return;
        }

        showToast(`Found ${mediaList.length} media items! Downloading...`, "info");

        // Trigger download for each item
        let downloadedCount = 0;
        mediaList.forEach((item, idx) => {
            const timestamp = new Date().toISOString().replace(/[-:T.]/g, "").slice(0, 14);
            const filename = `whatsapp_${item.type}_${timestamp}_${idx + 1}.${item.ext}`;

            // Try chrome downloads via background service worker
            if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    action: "download_media",
                    url: item.url,
                    filename: filename
                }, (response) => {
                    if (chrome.runtime.lastError || !response || !response.success) {
                        // Fallback to programmatic anchor download
                        triggerAnchorDownload(item.url, filename);
                    }
                });
            } else {
                // Fallback
                triggerAnchorDownload(item.url, filename);
            }
            downloadedCount++;
        });

        setTimeout(() => {
            showToast(`Successfully triggered ${downloadedCount} media downloads!`, "success");
        }, 1200);
    }

    function triggerAnchorDownload(url, filename) {
        try {
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            a.style.display = "none";
            document.body.appendChild(a);
            a.click();
            setTimeout(() => a.remove(), 1000);
        } catch (e) {
            console.error("Direct anchor download error:", e);
        }
    }

    function showToast(msg, type = "info") {
        let toast = document.getElementById(TOAST_ID);
        if (toast) toast.remove();

        toast = document.createElement("div");
        toast.id = TOAST_ID;

        const bgColor = type === "success" ? "#059669" : type === "warning" ? "#d97706" : "#2563eb";

        toast.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 12px 20px;
            background-color: ${bgColor};
            color: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
            font-weight: 600;
            border-radius: 12px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
            z-index: 99999;
            transition: all 0.3s ease;
        `;
        toast.textContent = msg;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 400);
        }, 3500);
    }

    // Expose for extension popup manual triggers if needed
    window.waMediaExtractorScan = scanAndDownloadMedia;
})();
