(() => {
    let styleSheet = document.createElement('style');
    document.head.appendChild(styleSheet);  // Before this, .sheet is null.
    // language=css
    styleSheet.sheet.insertRule('.accent-faint { font-size: 1px; line-height: normal; }', 0);
})()

function putAccent(containerElement, regex) {
    let walker = document.createTreeWalker(containerElement, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
        let match = regex.exec(walker.currentNode.nodeValue);
        if (match !== null) {
            walker.currentNode.innerHTML = '';
            const nodeBefore = document.createElement('span');
            const nodeAccent = nodeBefore.cloneNode();
            const nodeAfter = nodeBefore.cloneNode();
            nodeBefore.classList.add('accent-faint');
            nodeAccent.classList.add('accent-accent');
            nodeAfter.classList.add('accent-faint');
            nodeBefore.textContent = match[1];
            nodeAccent.textContent = match[2];
            nodeAfter.textContent = match[3];
            walker.currentNode.parentElement.insertBefore(nodeBefore, walker.currentNode);
            walker.currentNode.parentElement.insertBefore(nodeAccent, walker.currentNode);
            walker.currentNode.parentElement.insertBefore(nodeAfter, walker.currentNode);
            walker.currentNode.nodeValue = '';
        }
    }
}

function putAccentOnVMSURL(element) {
    putAccent(element, new RegExp('^(.+/)(build-vms-\\w+/[^/]+/\\d+)(/.*)$'));
}

function putAccentOnWebAdminURL(element) {
    putAccent(element, new RegExp('^(.+/)(build-webadmin-gitlab/[a-fA-F0-9]{8})([a-fA-F0-9]{32}.*)$'));
}

function putAccentOnCloudHost(element) {
    // test.mr-121.nxcloud.us.networkoptix.dev
    // cp-mr-8538.nxcloud.us.networkoptix.dev
    // nightly-develop.nxcloud.networkoptix.dev
    // test.nxcloud.us.networkoptix.dev
    putAccent(element, new RegExp('^()([-.0-9a-zA-Z]+\.nxcloud)(\.(?:us\.)?networkoptix\.dev)$'));
}
