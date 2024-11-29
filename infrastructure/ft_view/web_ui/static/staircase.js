class StaircaseSequence {
    constructor(splitFunc) {
        this.#splitFunc = splitFunc;
    }

    processElement(newElement) {
        this.#prevElement = this.#currentElement;
        this.#prevNodes = this.#currentNodes;
        this.#currentElement = newElement;
        this.#currentNodes = null;
        if (this.#currentElement.classList.contains('staircase-processed'))
            return
        this.#currentElement.classList.add('staircase-processed');
        let raw = this.#currentElement.textContent.trim();
        let parts = this.#splitFunc(raw);
        console.assert(parts.join('') === raw);
        this.#currentElement.innerHTML = '';
        for (let part of parts) {
            this.#currentElement.appendChild(document.createElement('span'));
            this.#currentElement.lastChild.classList.add('staircase-node');
            this.#currentElement.lastChild.textContent = part;
            this.#currentElement.lastChild.dataset['part'] = part;
        }
        this.#currentNodes = Array.from(this.#currentElement.querySelectorAll('.staircase-node'));
        this.#setupAndShow();
        this.#indentStaircase();
        if (this.#prevElement !== null) {
            this.#hideRepeated();
        }
    }

    #setupAndShow() {
        for (let i = 0; i < this.#currentNodes.length; i++) {
            this.#currentNodes[i].classList.add('staircase-' + i)
            this.#currentNodes[i].classList.add('staircase-show');
        }
    }

    #indentStaircase() {
        function indent(node, level) {
            let child = node.firstChild;

            while (level > 0) {
                let newChild = document.createElement('span');
                newChild.classList.add('staircase-indent');
                node.insertBefore(newChild, child);
                level--;
            }
        }

        for (let i = 0; i < this.#currentNodes.length; i++) {
            indent(this.#currentNodes[i], i);
        }
    }

    #hideRepeated() {
        for (let i = 0; ; i++) {
            if (i === this.#prevNodes.length) {
                break;
            }
            if (i === this.#currentNodes.length - 1) {
                // Leave at least one element.
                break;
            }
            if (this.#currentNodes[i].dataset['part'] !== this.#prevNodes[i].dataset['part']) {
                break;
            }
            this.#currentNodes[i].classList.add('staircase-hide');
            this.#currentNodes[i].classList.remove('staircase-show');
        }
    }

    #splitFunc;
    #prevElement = null;
    #currentElement = null;
    #currentNodes = null;
    #prevNodes = null;
}
