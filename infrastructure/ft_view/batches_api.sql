CREATE OR REPLACE FUNCTION pg_temp.jsonb_remove_by_prefix(prefix TEXT,jsonb_obj JSONB) RETURNS JSONB PARALLEL SAFE IMMUTABLE
BEGIN ATOMIC
    SELECT coalesce(jsonb_object_agg(key, value), '{}'::jsonb)
        FROM jsonb_each(jsonb_obj)
        WHERE NOT(key ^@ prefix);
END;

CREATE OR REPLACE FUNCTION pg_temp.batch_counters_aggregate(batch_cmdline jsonb) RETURNS jsonb
BEGIN ATOMIC
    SELECT coalesce(jsonb_object_agg('count.'::text || c.status, to_jsonb(c.count)), '{}'::jsonb)
        FROM (
            SELECT job.status, count(*) AS "count"
                FROM job JOIN batch_job bj ON bj.job = job.cmdline
                WHERE bj.batch = batch_cmdline
                GROUP BY job.status
            ) c;
END;

CREATE OR REPLACE FUNCTION pg_temp.batch_counters_update(batch_cmdline jsonb) RETURNS void
BEGIN ATOMIC
    UPDATE batch
        SET data = pg_temp.batch_counters_aggregate(batch_cmdline) || pg_temp.jsonb_remove_by_prefix('count.', data)
        WHERE cmdline = batch_cmdline;
END;

CREATE OR REPLACE FUNCTION pg_temp.batch_reschedule_failed_jobs(batch_cmdline jsonb, new_progress text, max_reruns int) RETURNS boolean LANGUAGE plpgsql AS $func$
DECLARE
    job_cmdline jsonb;
BEGIN
    IF (SELECT (data->>'count.failed')::int > max_reruns FROM batch WHERE cmdline = batch_cmdline) THEN
        RETURN FALSE;
    END IF;
    FOR job_cmdline IN
        SELECT job.cmdline
            FROM job
                JOIN batch_job ON job.cmdline = batch_job.job
            WHERE batch_job.batch = batch_cmdline
                AND job.status = ANY(ARRAY['created', 'failed', 'cancelled'])
        LOOP
            PERFORM pg_temp.job_update_status(new_progress, 'pending', job_cmdline);
        END LOOP;
    RETURN TRUE;
END;
$func$;


CREATE OR REPLACE FUNCTION pg_temp.start_batch(batch_cmdline jsonb, batch_data jsonb, batch_progress text, tests jsonb) RETURNS void AS $$
BEGIN
    CREATE TEMPORARY TABLE new_jobs ON COMMIT DROP AS
        SELECT *
            FROM jsonb_to_recordset(tests) AS t(cmdline jsonb, stage_url text, marks text[]);
    INSERT INTO job (cmdline, source, tags, progress, status)
        SELECT t.cmdline, t.stage_url, t.marks, batch_progress, 'pending'
            FROM new_jobs AS t
        ON CONFLICT (cmdline) DO NOTHING;
    INSERT INTO batch (created_at, cmdline, data)
        SELECT ((batch_data)->>'created_at')::timestamptz, batch_cmdline, batch_data
        ON CONFLICT (cmdline) DO NOTHING;
    INSERT INTO batch_job (batch, job)
        SELECT batch_cmdline, new_jobs.cmdline
            FROM new_jobs
        ON CONFLICT DO NOTHING;
    PERFORM pg_temp.batch_counters_update(batch_cmdline);
    PERFORM pg_temp.batch_reschedule_failed_jobs(batch_cmdline, batch_progress, 3);
END;
$$ LANGUAGE plpgsql;
