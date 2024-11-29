# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Reveal passwords and remove local path to OS image."""
import base64
import os.path
import sys
import xml.etree.cElementTree as ElementTree

_xml_ns = {
    'unattend': 'urn:schemas-microsoft-com:unattend',
    'wcm': 'http://schemas.microsoft.com/WMIConfig/2002/State',
    'cpi': 'urn:schemas-microsoft-com:cpi',
    }


def remove_image_path(tree):
    # Remove offline image path, which is local to machine this file was saved.
    image_attr = '{{{}}}source'.format(_xml_ns['cpi'])
    image_elem = tree.find('./cpi:offlineImage', _xml_ns)
    if image_elem.attrib[image_attr]:
        image_elem.attrib[image_attr] = ''
        return True
    return False


def reveal_passwords(tree):
    changed = False
    for elem in tree.getroot().findall('.//unattend:PlainText/..', _xml_ns):
        value = elem.find('./unattend:Value', _xml_ns)
        flag = elem.find('./unattend:PlainText', _xml_ns)
        if flag.text == 'false':
            encoded = value.text
            decoded = base64.b64decode(encoded).decode('utf16')
            tag = elem.tag.replace('{' + _xml_ns['unattend'] + '}', '')
            assert decoded.endswith(tag)
            value.text = decoded[:-len(tag)]
            flag.text = 'true'
            changed = True
    return changed


def main(*args):
    for alias, url in _xml_ns.items():
        ElementTree.register_namespace('' if alias == 'unattend' else alias, url)

    success = True

    for root, _dirs, files in os.walk(os.path.dirname(__file__)):
        for file in files:
            if not file.endswith('.xml'):
                continue
            path = os.path.join(root, file)
            tree = ElementTree.parse(path)
            changed = False
            if reveal_passwords(tree):
                print("Passwords were not revealed: {}".format(path), file=sys.stderr)
                changed = True
            if remove_image_path(tree):
                print("Image path was specified: {}".format(path), file=sys.stderr)
                changed = True

            if '--check' in args:
                if changed:
                    print("Not standardized: {}".format(path), file=sys.stderr)
                    success = False
                else:
                    print("Standardized: {}".format(path), file=sys.stderr)
            else:
                if changed:
                    print("Write: {}".format(path), file=sys.stderr)
                    tree.write(path)
                else:
                    print("Unchanged: {}".format(path), file=sys.stderr)

    return 0 if success else 1


if __name__ == '__main__':
    exit(main(sys.argv[1:]))
