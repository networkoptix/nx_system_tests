SELECT actual, expected, actual = expected AS success FROM (VALUES
    (pg_temp.run_message_to_tsvector($$'System' shown$$), $$'''':1 System:2 '''':3 shown:4$$::tsvector),
    (pg_temp.run_message_to_tsvector(''), ''::tsvector),
    (pg_temp.run_message_to_tsvector(NULL), ''::tsvector),
    (pg_temp.run_metadata_to_tsvector('{"k": "v"}'), 'k=v'::tsvector),
    (pg_temp.run_metadata_to_tsvector('{"k": "v", "p":  "q"}'), 'k=v p=q'::tsvector),
    (pg_temp.run_metadata_to_tsvector('{}'::jsonb), ''::tsvector),
    (pg_temp.run_metadata_to_tsvector(NULL), ''::tsvector)
) AS outcome(actual, expected);

SELECT actual, expected, actual = expected AS success FROM (VALUES
    (pg_temp.run_message_to_tsquery($$'System' shown$$), $$'''' <-> System <-> '''' <-> shown$$::tsquery),
    (pg_temp.run_message_to_tsquery(''), ''::tsquery),
    (pg_temp.run_message_to_tsquery(NULL), ''::tsquery),
    (pg_temp.run_metadata_to_tsquery('{"k": "v"}'), 'k=v'::tsquery),
    (pg_temp.run_metadata_to_tsquery('{"k": "v", "p":  "q"}'), 'k=v & p=q'::tsquery),
    (pg_temp.run_metadata_to_tsquery('{}'::jsonb), ''::tsquery),
    (pg_temp.run_metadata_to_tsquery(NULL), ''::tsquery)
) AS outcome(actual, expected);

SELECT vector, query, expected, vector @@ query AS actual, (vector @@ query) IS NOT DISTINCT FROM expected AS success FROM (VALUES
    (TRUE, pg_temp.run_message_to_tsvector($$'New System' is not shown$$), pg_temp.run_message_to_tsquery($$'New System'$$)),
    (TRUE, pg_temp.run_metadata_to_tsvector('{"k": "v", "p":  "q"}'), pg_temp.run_metadata_to_tsquery('{"k": "v"}')),
    (FALSE, pg_temp.run_metadata_to_tsvector('{"k": "V", "p":  "q"}'), pg_temp.run_metadata_to_tsquery('{"k": "v"}')),
    (TRUE, pg_temp.run_to_tsvector('{"k": "v", "p":  "q"}', 'qwe asd zxc'), pg_temp.run_to_tsquery('{"k": "v"}', 'asd zxc')),
    (FALSE, pg_temp.run_to_tsvector('{"k": "v", "p":  "q"}', 'qwe asd zxc'), pg_temp.run_to_tsquery('{"k": "v"}', 'qwe zxc'))
) AS outcome(expected, vector, query);
