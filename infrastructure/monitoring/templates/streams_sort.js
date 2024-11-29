document.addEventListener("DOMContentLoaded", function() {
    const headers = document.querySelectorAll("thead th");
    let sort_table = new SortTable(headers);
    headers.forEach((header, index) => {
        header.addEventListener("click", () => sort_table.applySort(index, nextSortState(header)));
    });
    sort_table.applySort(...parseQuery());
});

const SortOrderEnum = {
    'ASC': 0x2191,
    'DESC': 0x2193,
    'NONE': 0x21C5,
};

class SortTable{
    constructor(headers)
    {
        this.#headers = headers;
        this.#table = document.querySelector("tbody");
        this.#rows = Array.from(this.#table.querySelectorAll("tr"));
    }

    applySort(column_index, next_state) {
        this.#index = column_index;
        this.#next_state = next_state;
        this.#sortRows();
        this.#updateURL();
        this.#updateSortIcons();
    }

    #sortRows() {
        const sort_function = this.#getSortFunction(this.#rows[0]);
        this.#rows.sort(sort_function(this.#index, this.#next_state));
        const fragment = document.createDocumentFragment();
        this.#rows.forEach(row => fragment.appendChild(row));
        this.#table.appendChild(fragment);
    }

    #getSortFunction(inspected_row) {
        const cell = inspected_row.cells[this.#index].textContent;
        return isNaN(parseFloat(cell)) ? sortTableLexicalOrder : sortTableNumeralOrder;
    }

    #updateURL() {
        const query = new URLSearchParams(window.location.search);
        query.set('column_id', parseInt(this.#index));
        query.set('reverse', this.#next_state);
        const updated_query = window.location.pathname + '?' + query.toString();
        window.history.replaceState(null, '', updated_query);
    }

    #updateSortIcons() {
        this.#headers.forEach((header, index) => {
            const element = header.querySelector('.sort-arrow');
            if (index === this.#index) {
                const sorting_code = this.#next_state ? SortOrderEnum.DESC : SortOrderEnum.ASC;
                element.innerHTML = String.fromCharCode(sorting_code);
            }
            else {
                element.innerHTML = String.fromCharCode(SortOrderEnum.NONE);
            }
        });
    }
    #headers;
    #rows;
    #table;
    #index = null;
    #next_state = null;
}

function nextSortState(header) {
    const default_sort_order = SortOrderEnum.DESC;
    const element = header.querySelector('.sort-arrow')
    return element.innerHTML.charCodeAt(0) !== default_sort_order;
}

function parseQuery() {
    const default_column_index = 3;
    const query = new URLSearchParams(window.location.search);
    const query_column_id = parseInt(query.get('column_id') ?? default_column_index);
    const sort_order = (query.get('reverse') ?? 'true') === 'true';
    return [query_column_id, sort_order];
}

function sortTableLexicalOrder(column_index, reverse) {
    return (row_1, row_2) => {
        const cell_1 = row_1.cells[column_index].textContent;
        const cell_2 = row_2.cells[column_index].textContent;
        const isLess = cell_1.localeCompare(cell_2);
        return reverse ? -isLess : isLess;
    }
}

function sortTableNumeralOrder(column_index, reverse) {
    return (row_1, row_2) => {
        const cell_1 = row_1.cells[column_index].textContent;
        const cell_2 = row_2.cells[column_index].textContent;
        const isLess = parseFloat(cell_1) - parseFloat(cell_2);
        return reverse ? -isLess : isLess;
    }
}
