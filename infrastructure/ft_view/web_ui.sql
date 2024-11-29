CREATE OR REPLACE FUNCTION pg_temp.json_slice(o jsonb, prefix text) RETURNS jsonb STRICT IMMUTABLE PARALLEL SAFE
BEGIN ATOMIC
    SELECT jsonb_build_object(prefix, jsonb_object_agg(key, value))
    FROM jsonb_each(o)
    WHERE key ^@ (prefix || '.');
END;

CREATE OR REPLACE FUNCTION pg_temp.job_runs(cmdline jsonb) RETURNS jsonb STRICT
BEGIN ATOMIC
    SELECT coalesce(jsonb_agg((pg_temp.json_slice(run_json, 'proc') || pg_temp.json_slice(run_json, 'report')) ORDER BY run_json->'proc.started_at'), '[]'::jsonb)
    FROM run
    WHERE run_cmdline = cmdline;
END;
