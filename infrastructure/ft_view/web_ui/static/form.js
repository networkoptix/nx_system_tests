function jsonToForm(formElement, json) {
    let data = JSON.parse(json);
    for (let key in data) {
        let input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        input.value = data[key];
        formElement.appendChild(input);
    }
    return formElement;
}
