CREATE OR REPLACE FUNCTION pg_temp.job_counters(multiplicity int, job_cmdline jsonb) RETURNS jsonb
BEGIN ATOMIC
    SELECT jsonb_build_object('count.' || status, multiplicity)
        FROM job
        WHERE cmdline = job_cmdline;
END;

CREATE OR REPLACE FUNCTION pg_temp.jsonb_numeric_sum(current jsonb, change jsonb) RETURNS jsonb PARALLEL SAFE IMMUTABLE
RETURN CASE
    WHEN jsonb_typeof(current) = 'number' AND jsonb_typeof(change) = 'number'
        THEN to_jsonb(current::numeric + change::numeric)
    WHEN jsonb_typeof(current) = 'null'
        THEN change
    WHEN jsonb_typeof(change) = 'null'
        THEN current
    ELSE COALESCE(current, change)
    END;

CREATE OR REPLACE FUNCTION pg_temp.jsonb_numeric_merge(current jsonb, change jsonb) RETURNS jsonb PARALLEL SAFE IMMUTABLE
BEGIN ATOMIC
    SELECT jsonb_object_agg(key, pg_temp.jsonb_numeric_sum(current.value, change.value))
        FROM jsonb_each(current) current
            FULL OUTER JOIN jsonb_each(change) change
                USING (key);
END;

CREATE OR REPLACE FUNCTION pg_temp.job_update_status(new_progress text, new_status text, job_cmdline jsonb) RETURNS void AS $func$
DECLARE
    delta_before jsonb;
    delta_after jsonb;
    delta jsonb;
BEGIN
    SELECT pg_temp.job_counters(-1, job_cmdline)
        INTO delta_before;
    UPDATE job
        SET (progress, status) = (coalesce(new_progress, progress), new_status)
        WHERE job.cmdline = job_cmdline;
    SELECT pg_temp.job_counters(1, job_cmdline)
        INTO delta_after;
    SELECT pg_temp.jsonb_numeric_merge(delta_after, delta_before)
        INTO delta;
    UPDATE batch
        SET data = pg_temp.jsonb_numeric_merge(data, delta)
        FROM batch_job
        WHERE batch_job.job = job_cmdline
        AND batch.cmdline = batch_job.batch;
END;
$func$ LANGUAGE plpgsql;
