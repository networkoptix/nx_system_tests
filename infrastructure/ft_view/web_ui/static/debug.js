(() => {
    let styleSheet = document.createElement('style');
    document.head.appendChild(styleSheet);  // Before this, .sheet is null.
    styleSheet.disabled = localStorage.getItem('debug') !== 'enabled';
    styleSheet.sheet.insertRule('.debug { display: none; }', 0);
    document.addEventListener('keyup', (event) => {
        if (!(event.code === 'KeyD' && event.ctrlKey && event.altKey && event.shiftKey)) {
            return;
        }
        const was_enabled = localStorage.getItem('debug') === 'enabled';
        localStorage.setItem('debug', was_enabled ? 'disabled' : 'enabled');
        styleSheet.disabled = was_enabled;
        event.preventDefault();
    });
})()
