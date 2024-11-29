CREATE FUNCTION pg_temp.store_update(raw jsonb) RETURNS void
BEGIN ATOMIC
    SELECT pg_temp.job_update_status(NULL, raw->'run_data'->>'report.status', raw->'run_cmdline');
    INSERT INTO run(
        run_cmdline,
        run_json,
        run_index,
        run_username,
        run_hostname,
        run_started_at,
        run_pid,
        run_ft_revision,
        run_url,
        run_vms_version,
        run_vms_url,
        run_vms_branch,
        run_vms_revision,
        run_args,
        run_duration_sec,
        run_message,
        run_artifacts,
        run_ticket
        )
    VALUES (
        raw->'run_cmdline',
        raw->'run_data' || jsonb_build_object('stage_status', raw->'run_data'->>'report.status'),
        pg_temp.run_to_tsvector(raw->'run_data', raw->>'run_message'),
        raw->'run_data'->>'proc.username',
        raw->'run_data'->>'proc.hostname',
        (raw->'run_data'->>'proc.started_at')::timestamptz,
        (raw->'run_data'->>'proc.pid')::integer,
        raw->'run_cmdline'->>'env.COMMIT',
        raw->'run_data'->>'report.run_url',
        raw->'run_data'->>'build_info.version',
        raw->'run_cmdline'->>'opt.--installers-url',
        raw->'run_data'->>'build_info.opt.--installers-url.branch',
        raw->'run_data'->>'build_info.opt.--installers-url.changeSet',
        raw->>'run_args',
        (raw->'run_data'->>'report.duration_sec')::float,
        raw->>'run_message',
        array(SELECT jsonb_array_elements_text(raw->'artifact_urls')),
        raw->'run_data'->>'ticket'
        )
    ON CONFLICT (run_username, run_hostname, run_started_at, run_pid) DO UPDATE SET
        run_cmdline = coalesce(run.run_cmdline, excluded.run_cmdline),
        run_json = coalesce(run.run_json || excluded.run_json, excluded.run_json, run.run_json),
        run_index = excluded.run_index,
        run_ft_revision = coalesce(run.run_ft_revision, excluded.run_ft_revision),
        run_url = coalesce(run.run_url, excluded.run_url),
        run_vms_version = coalesce(run.run_vms_version, excluded.run_vms_version),
        run_vms_url = coalesce(run.run_vms_url, excluded.run_vms_url),
        run_vms_branch = coalesce(run.run_vms_branch, excluded.run_vms_branch),
        run_vms_revision = coalesce(run.run_vms_revision, excluded.run_vms_revision),
        run_args = coalesce(run.run_args, excluded.run_args),
        run_duration_sec = coalesce(run.run_duration_sec, excluded.run_duration_sec),
        run_message =
            CASE
                WHEN run.run_message IS NULL
                    THEN excluded.run_message
                WHEN excluded.run_message IS NULL
                    THEN run.run_message
                ELSE concat(run.run_message, E'\n', repeat('-', 80), E'\n', excluded.run_message)
                END,
        run_artifacts = array_cat(run.run_artifacts, excluded.run_artifacts),
        run_ticket = coalesce(run.run_ticket, excluded.run_ticket);
END;
