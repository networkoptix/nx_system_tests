---
Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
---
# Description of UNIX-socket api

**qcow2target** is a demon which shares qcow2 disks via `iSCSI` protocol.

## Communication format for all requests

The commands are being set via UNIX domain socket using TCP protocol.
The data MUST be sent as utf-8 encoded string terminated with `\n` (line separator)
containing JSON of the specified format:
```json
{
    "type": "<string type value>",
    "command": {
        "command specific data": ""
    }
}
```
* `type` MUST be string value, available values would be specified further
* `command` - contains any JSON dictionary, format varies for each `type` value.

Replies are sent as utf-8 encoded string terminated with `\n` (line separator)
containing JSON of the specified format:

```json
{
  "error": "",
  "result": {
    "targets": {
      "iqn.nx.2018.com:arms:rpi1": {
        "luns": [{"lun1":  {"disk":  "ubuntu18.qcow2"}}]
      }
    }
  }
}
```

* `error` - contains either a string error description, if string is empty - request is successful.
* `result` - JSON dictionary, contains all requested data or additional info for error.


## Request types:
* `ATTACH`
* `DETACHLUN`
* `ADDTARGET`
* `DELETETARGET`
* `CLEARTARGET`
* `LIST`


### `ATTACH` attach existing QCOW2 disk to iSCSI target
Format:
```json
{
  "disk_path": "/tmp/disks/test.qcow2",
  "target_name": "iqn.nx.2018.com:arms:rpi1"
}
```
* `disk_path` - path to the qcow2 disk, MUST be relative to iSCSI disks root
* `target_name` - string iSCSI target name.

Response:
```json
{
  "lun_id": 2
}
```

### `DETACHLUN` detach QCOW2 disk from LUN by lun id

Format:
```json
{
  "lun_id": 1,
  "target_name": "<target_name>"
}
```

Response:
```json
{
  "file_path": "/var/sample/disk.qcow2"
}
```
### `ADDTARGET` adds target to iSCSI daemon

Format:
```json
{
  "target_name": "<string target name>"
}
```


Response:

empty

### `DELETETARGET` delete target

Format:
```json
{
  "target_name": "<string target name>"
}
```
Response:
empty

### `CLEARTARGET` detaches all LUNs from the target

Format:
```json
{
  "target_name": "<string target name>"
}
```
Response:
```json
{
  "freed_logical_unit_paths": ["/var/tmp/disk.qcow2"] 
}
```

### `LIST` all targets
Format:
empty

Response:
```json
{
  "<target_name>": {
    "target_id": 1,
    "logical_units": [
      {"logical_unit_id": 1, "file_path": "<optional string disk path>"}
    ],
    "has_connections": true,
    "it_nexuses": ["string it nexus 1"]
  }
}
```
Contains dict with target names as keys and records with list of LUNs, and state indicating whether
there are connected initiators to the target, also contains list of it nexus names.
Each LUN contains optional disk path.

