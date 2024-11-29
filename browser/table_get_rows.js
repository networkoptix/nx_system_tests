function irrelevant(arguments) {
    const rows = [];
    for (const tableRow of arguments[0].rows) {
        const cells = [];
        for (const cell of tableRow.cells) {
            if (cell.tagName.toLowerCase() === 'td') cells.push(cell);
        }
        if (cells.length !== 0) rows.push(cells);
    }
    return rows;
}
