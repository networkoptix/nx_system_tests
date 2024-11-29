---
Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
---
# FT View DB

## DB schema

Command:

```sh
ssh $DB_HOST sudo -Hu ft pg_dump --host=127.0.0.1 --username=ft_view_read_only --dbname=ft_view --schema-only
```

Results go into the schema SQL file unaltered.