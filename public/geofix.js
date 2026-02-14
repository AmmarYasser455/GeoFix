/* ============================================================
   GeoFix 2.1 — Custom JavaScript
   Keyboard shortcuts and UI enhancements for Chainlit
   ============================================================ */

(function () {
    'use strict';

    // ── Keyboard Shortcuts ──────────────────────────────────────

    document.addEventListener('keydown', function (e) {
        // Ctrl+/ or Cmd+/ → Focus chat input
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
            e.preventDefault();
            const textarea = document.querySelector('textarea');
            if (textarea) textarea.focus();
        }

        // Escape → Blur chat input
        if (e.key === 'Escape') {
            const textarea = document.querySelector('textarea');
            if (textarea && document.activeElement === textarea) {
                textarea.blur();
            }
        }
    });

    // ── Smooth entry animation for new messages ─────────────────

    const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType === 1 && node.classList) {
                    // Add subtle entrance animation to new message elements
                    if (node.querySelector && node.querySelector('.cl-message')) {
                        const msg = node.querySelector('.cl-message');
                        msg.style.animation = 'msgSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1)';
                    }
                }
            });
        });
    });

    // Start observing once the chat container is ready
    function initObserver() {
        const chatContainer = document.querySelector('[class*="messages"], main');
        if (chatContainer) {
            observer.observe(chatContainer, { childList: true, subtree: true });
        } else {
            // Retry after DOM is ready
            setTimeout(initObserver, 500);
        }
    }

    // ── Console branding ────────────────────────────────────────

    console.log(
        '%c🌍 GeoFix 2.1 %c AI-Powered Geospatial QC',
        'background: #2dd4bf; color: #09090b; padding: 4px 8px; border-radius: 4px 0 0 4px; font-weight: 700;',
        'background: #18181b; color: #f4f4f5; padding: 4px 8px; border-radius: 0 4px 4px 0;'
    );

    // Init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initObserver);
    } else {
        initObserver();
    }
})();
