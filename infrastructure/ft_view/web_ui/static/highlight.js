function highlightWords(containerElement) {
    let words = [
        'win',
        'ubuntu',
        'v0',
        'v1',
        'v2',
        'v3',
        '.ERROR.log',
        '.backtrace.txt',
        '-log_file_error.log',
        '.mp4',
    ];

    let walker = document.createTreeWalker(containerElement, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
        processOneTextNode(walker.currentNode, words);
    }

    function processOneTextNode(node, words) {
        while (true) {
            let find = nextOccurrence(node.data, words);
            if (find.found.length <= 0)
                break;
            if (find.skipped.length > 0)
                node.parentElement.insertBefore(createGapElement(find.skipped), node);
            node.parentElement.insertBefore(createWordElement(find.found), node);
            node.data = find.remainder;
        }
    }

    function nextOccurrence(text, words) {
        for (let i = 0; i < text.length; ++i)
            for (let w of words)
                if (text.substring(i, i + w.length) === w)
                    return {
                        skipped: text.substring(0, i),
                        found: w,
                        remainder: text.substring(i + w.length),
                    };
        return {
            skipped: text,
            found: '',
            remainder: '',
        };
    }

    function createGapElement(word) {
        let newNode = document.createElement('span');
        newNode.innerHTML = word;
        newNode.classList.add('highlight-gap');
        return newNode;
    }

    function createWordElement(word) {
        let newNode = document.createElement('span');
        newNode.innerHTML = word;
        newNode.classList.add('highlight-' + word);
        newNode.classList.add('highlight-find');
        return newNode;
    }
}
