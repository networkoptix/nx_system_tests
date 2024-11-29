function uuid4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
    .replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function make_response(obj, metatype) {
    const id = `obj-${uuid4()}`;
    return {
        'id': id,
        'type': typeof obj,
        'result': __testkit_cache[id] = obj,
        'metatype': metatype || null
    };
}

function get_object_metatype(obj, name) {
    try {
        return testkit.wrap(obj).metaInfo(name)['type'];
    } catch (e) {
        return null;
    }
}

function get_method_return_type(obj, name) {
    try {
        return testkit.wrap(obj).metaInfo(name)['return_type'];
    } catch (e) {
        return null;
    }
}

function find_objects(locator) {
    let results = [];
    testkit.find(locator).forEach((obj) => {
        results.push(make_response(obj));
    });
    return results;
}

function find_object(locator) {
    const occurrence = locator['occurrence'];
    delete locator['occurrence'];

    const objects = testkit.find(locator);

    if (objects.length === 1)
        return make_response(objects[0]);
    else if (occurrence && occurrence > 0)
        return make_response(objects[occurrence - 1]);
    else if (objects.length === 2 && JSON.stringify(objects[0]) === JSON.stringify(objects[1]))
        return make_response(objects[0]);
    else if (objects.length > 1)
        return {
            'error': 1,
            'errorString': 'Found several elements',
            'result': JSON.stringify(objects)
        };
    else
        return null;
}

function set_object_property(obj_id, name, value) {
    __testkit_cache[obj_id][name] = value;
}

function get_object_property(obj_id, name) {
    const obj = __testkit_cache[obj_id];
    if (typeof obj === 'function')
        return null;
    return make_response(obj[name], get_object_metatype(obj, name));
}

function call_object_method(obj_id, name, args) {
    const obj = __testkit_cache[obj_id];
    let obj_method = obj[name];
    if (typeof obj_method !== 'function') {
        obj_method = testkit.wrap(obj)[name];
        if (typeof obj_method !== 'function')
            return null;
    }
    return make_response(
        (args) ? obj_method(args) : obj_method(),
        get_method_return_type(obj, name)
    );
}

function dump(obj_id) {
    const obj = __testkit_cache[obj_id];
    return {'result': JSON.stringify(obj)};
}
