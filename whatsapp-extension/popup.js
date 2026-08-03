document.addEventListener("DOMContentLoaded", () => {
    const scanBtn = document.getElementById("scan-btn");
    const statusText = document.getElementById("status-text");

    // Check current active tab
    if (typeof chrome !== "undefined" && chrome.tabs) {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs.length > 0) {
                const currentUrl = tabs[0].url || "";
                if (!currentUrl.includes("web.whatsapp.com")) {
                    statusText.textContent = "Please open web.whatsapp.com";
                    statusText.parentElement.style.color = "#f87171";
                    scanBtn.disabled = true;
                    scanBtn.style.opacity = "0.5";
                }
            }
        });
    }

    scanBtn.addEventListener("click", () => {
        if (typeof chrome !== "undefined" && chrome.tabs) {
            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                if (tabs[0] && tabs[0].id) {
                    chrome.scripting.executeScript({
                        target: { tabId: tabs[0].id },
                        func: () => {
                            if (window.waMediaExtractorScan) {
                                window.waMediaExtractorScan();
                            } else {
                                alert("WhatsApp Extractor content script is loading. Please refresh WhatsApp Web tab.");
                            }
                        }
                    });
                }
            });
        }
    });
});
