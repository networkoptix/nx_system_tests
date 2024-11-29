function highlightCurrentLink(containerElement) {
    for (const linkElement of containerElement.querySelectorAll('a[href]')) {
        if (isCurrentURLLink(linkElement)) {
            markAsCurrentLink(linkElement);
        }
    }

    function markAsCurrentLink(element) {
        element.classList.add('current');
    }

    function isCurrentURLLink(node) {
        // node.href is always a full URL.
        // node.attributes['href'] is the literal attribute, which may be any.
        return normalizeURL(node.href) === normalizeURL(window.location);
    }

    function normalizeURL(url) {
        const u = new URL(url);
        u.search = new URLSearchParams([...new URLSearchParams(u.search)].sort()).toString();
        return u.toString();
    }
}
