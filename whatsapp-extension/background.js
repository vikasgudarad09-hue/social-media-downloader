// Service worker for WhatsApp Web Media Extractor Chrome Extension

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "download_media") {
        const { url, filename } = request;
        
        if (!url) {
            sendResponse({ success: false, error: "No URL provided" });
            return true;
        }

        try {
            chrome.downloads.download({
                url: url,
                filename: filename || `whatsapp_media_${Date.now()}`,
                saveAs: false
            }, (downloadId) => {
                if (chrome.runtime.lastError) {
                    console.error("Download failed:", chrome.runtime.lastError.message);
                    sendResponse({ success: false, error: chrome.runtime.lastError.message });
                } else {
                    sendResponse({ success: true, downloadId });
                }
            });
        } catch (err) {
            console.error("Error executing download:", err);
            sendResponse({ success: false, error: err.message });
        }
        return true; // Keep message channel open for async response
    }
});
