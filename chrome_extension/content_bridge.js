// Bridge between the Next.js page context and the Extension's background service worker

window.addEventListener("message", (event) => {
    // Only accept messages from the same frame
    if (event.source !== window) return;

    if (event.data && event.data.type === "FROM_PAGE_TO_EXT") {
        // Forward to background.js
        chrome.runtime.sendMessage(event.data.message, (response) => {
            // Check for communication errors to prevent the orange error badge
            if (chrome.runtime.lastError) {
                console.warn("Extension communication error:", chrome.runtime.lastError.message);
                window.postMessage({ 
                    type: "FROM_EXT_TO_PAGE", 
                    id: event.data.id, 
                    response: { success: false, error: chrome.runtime.lastError.message } 
                }, "*");
                return;
            }
            // Send response back to the page
            window.postMessage({ 
                type: "FROM_EXT_TO_PAGE", 
                id: event.data.id, 
                response: response 
            }, "*");
        });
    }
});

// Let the web page know the extension is active without violating CSP
document.documentElement.setAttribute('data-naver-scraper-ext-installed', 'true');
