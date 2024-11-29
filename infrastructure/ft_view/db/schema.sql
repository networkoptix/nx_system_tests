--
-- PostgreSQL database dump
--

-- Dumped from database version 14.13 (Ubuntu 14.13-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.13 (Ubuntu 14.13-0ubuntu0.22.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: stage_status; Type: TYPE; Schema: public; Owner: ft_view
--

CREATE TYPE public.stage_status AS ENUM (
    'unknown',
    'failed',
    'skipped',
    'passed',
    'cancelled',
    'running'
);


ALTER TYPE public.stage_status OWNER TO ft_view;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: batch; Type: TABLE; Schema: public; Owner: ft_view
--

CREATE TABLE public.batch (
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    cmdline jsonb NOT NULL,
    data jsonb NOT NULL,
    CONSTRAINT batch_cmdline_is_object CHECK ((jsonb_typeof(cmdline) = 'object'::text))
);


ALTER TABLE public.batch OWNER TO ft_view;

--
-- Name: batch_job; Type: TABLE; Schema: public; Owner: ft_view
--

CREATE TABLE public.batch_job (
    batch jsonb NOT NULL,
    job jsonb NOT NULL
);


ALTER TABLE public.batch_job OWNER TO ft_view;

--
-- Name: job; Type: TABLE; Schema: public; Owner: ft_view
--

CREATE TABLE public.job (
    url text,
    status text DEFAULT 'created'::text NOT NULL,
    progress text DEFAULT 'created'::text NOT NULL,
    cmdline jsonb NOT NULL,
    tags text[] DEFAULT ARRAY[]::text[] NOT NULL,
    source text,
    CONSTRAINT job_cmdline_is_object CHECK ((jsonb_typeof(cmdline) = 'object'::text))
);


ALTER TABLE public.job OWNER TO ft_view;

--
-- Name: run; Type: TABLE; Schema: public; Owner: ft_view
--

CREATE TABLE public.run (
    run_username text NOT NULL,
    run_hostname text NOT NULL,
    run_started_at timestamp with time zone NOT NULL,
    run_args text,
    run_ft_revision text,
    run_vms_version text,
    run_vms_revision text,
    run_url text,
    run_stages_total integer DEFAULT 0 NOT NULL,
    run_stages_passed integer DEFAULT 0 NOT NULL,
    run_stages_skipped integer DEFAULT 0 NOT NULL,
    run_vms_url text COLLATE pg_catalog."C",
    run_stages_failed integer DEFAULT 0 NOT NULL,
    run_vms_branch text,
    run_pid integer,
    run_duration_sec double precision,
    run_message text,
    run_ticket text,
    run_artifacts text[] DEFAULT ARRAY[]::text[] NOT NULL,
    run_json jsonb NOT NULL,
    run_cmdline jsonb NOT NULL,
    run_index tsvector NOT NULL,
    CONSTRAINT run_cmdline_is_object CHECK ((jsonb_typeof(run_cmdline) = 'object'::text)),
    CONSTRAINT run_json_is_object CHECK ((jsonb_typeof(run_json) = 'object'::text))
);


ALTER TABLE public.run OWNER TO ft_view;

--
-- Name: clean_up_runs(interval, interval); Type: FUNCTION; Schema: public; Owner: ft_view
--

CREATE FUNCTION public.clean_up_runs(retention interval, size interval) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    oldest timestamptz;
    deleted_runs integer;
BEGIN
    ASSERT retention >= '60 days'::interval;
    ASSERT size <= '1 day'::interval;
    oldest := (
        SELECT run_started_at
        FROM run
        ORDER BY run_started_at
        LIMIT 1
        );
    DELETE
    FROM run
    WHERE run_started_at < least(now() - retention, oldest + size);
    GET DIAGNOSTICS deleted_runs = ROW_COUNT;
    RETURN deleted_runs;
END
$$;


ALTER FUNCTION public.clean_up_runs(retention interval, size interval) OWNER TO ft_view;

--
-- Name: clean_up_stages(interval, interval); Type: FUNCTION; Schema: public; Owner: ft_view
--

CREATE FUNCTION public.clean_up_stages(retention interval, size interval) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    oldest timestamptz;
    deleted_stages integer;
BEGIN
    ASSERT retention >= '60 days'::interval;
    ASSERT size <= '1 day'::interval;
    oldest := (
        SELECT run_started_at
        FROM stage
        ORDER BY run_started_at
        LIMIT 1
        );
    DELETE
    FROM stage
    WHERE run_started_at < least(now() - retention, oldest + size);
    GET DIAGNOSTICS deleted_stages = ROW_COUNT;
    RETURN deleted_stages;
END
$$;


ALTER FUNCTION public.clean_up_stages(retention interval, size interval) OWNER TO ft_view;

--
-- Name: pop_job(text, text, text); Type: FUNCTION; Schema: public; Owner: ft_view
--

CREATE FUNCTION public.pop_job(machinery text, progress_prefix text, new_progress text) RETURNS SETOF public.job
    LANGUAGE plpgsql
    AS $$
DECLARE
    -- A job may be updated after selecting jobs but before updating the batch.
    cursor CURSOR FOR
        SELECT *
        FROM job j
        WHERE (cmdline->>'env.MACHINERY') COLLATE "C" = pop_job.machinery
            AND progress COLLATE "C" >= pop_job.progress_prefix
            AND progress COLLATE "C" < left(pop_job.progress_prefix, -1) || chr(ascii(right(pop_job.progress_prefix, 1)) + 1)
        ORDER BY (cmdline->>'env.MACHINERY') COLLATE "C", progress COLLATE "C"
        LIMIT 1 FOR UPDATE SKIP LOCKED;
BEGIN
    FOR r IN cursor
        LOOP
            UPDATE job
            SET progress = pop_job.new_progress
            WHERE CURRENT OF cursor;
            RETURN NEXT r;
        END LOOP;
END;
$$;


ALTER FUNCTION public.pop_job(machinery text, progress_prefix text, new_progress text) OWNER TO ft_view;

--
-- Name: stages_by_tag(text, text); Type: FUNCTION; Schema: public; Owner: ft_view
--

CREATE FUNCTION public.stages_by_tag(revision text, tag text) RETURNS text[]
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN (
        SELECT array_agg(mark.stage_name)
        FROM mark
        WHERE mark.run_ft_revision = revision
            AND tag = ANY (mark.marks)
        );
END;
$$;


ALTER FUNCTION public.stages_by_tag(revision text, tag text) OWNER TO ft_view;

--
-- Name: tags_by_stage(text, text); Type: FUNCTION; Schema: public; Owner: ft_view
--

CREATE FUNCTION public.tags_by_stage(revision text, stage text) RETURNS text[]
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN (
        SELECT mark.marks
        FROM mark
        WHERE mark.run_ft_revision = revision
            AND mark.stage_name = stage
        );
END;
$$;


ALTER FUNCTION public.tags_by_stage(revision text, stage text) OWNER TO ft_view;

--
-- Name: update_run(json); Type: FUNCTION; Schema: public; Owner: ft_view
--

CREATE FUNCTION public.update_run(stage_data json) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO run(
        run_cmdline,
        run_json,
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
        run_stages_total,
        run_stages_passed,
        run_stages_failed,
        run_stages_skipped,
        run_artifacts
        )
    VALUES (
        (stage_data -> 'run_cmdline')::json,
        stage_data,
        stage_data ->> 'run_username',
        stage_data ->> 'run_hostname',
        (stage_data ->> 'run_started_at_iso')::timestamptz,
        coalesce((stage_data ->> 'run_pid')::integer, -abs(hashtext(stage_data ->> 'run_args')), 0),
        stage_data ->> 'run_ft_revision',
        stage_data ->> 'run_url',
        stage_data ->> 'run_vms_version',
        stage_data ->> 'run_vms_url',
        stage_data ->> 'run_vms_branch',
        stage_data ->> 'run_vms_revision',
        stage_data ->> 'run_args',
        (stage_data ->> 'run_duration_sec')::float,
        stage_data ->> 'run_message',
        coalesce(stage_data ->> 'run_stages_total', '0')::integer,
        coalesce(stage_data ->> 'run_stages_passed', '0')::integer,
        coalesce(stage_data ->> 'run_stages_failed', '0')::integer,
        coalesce(stage_data ->> 'run_stages_skipped', '0')::integer,
        array(SELECT json_array_elements_text(stage_data -> 'artifact_urls'))
        )
    ON CONFLICT (run_username, run_hostname, run_started_at, run_pid) DO UPDATE SET
        run_cmdline = coalesce(run.run_cmdline, excluded.run_cmdline),
        run_json = coalesce(run.run_json || excluded.run_json, excluded.run_json, run.run_json),
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
        run_stages_total = run.run_stages_total + excluded.run_stages_total,
        run_stages_passed = run.run_stages_passed + excluded.run_stages_passed,
        run_stages_failed = run.run_stages_failed + excluded.run_stages_failed,
        run_stages_skipped = run.run_stages_skipped + excluded.run_stages_skipped,
        run_artifacts = array_cat(run.run_artifacts, excluded.run_artifacts);
END;
$$;


ALTER FUNCTION public.update_run(stage_data json) OWNER TO ft_view;

--
-- Name: batch batch_cmdline_key; Type: CONSTRAINT; Schema: public; Owner: ft_view
--

ALTER TABLE ONLY public.batch
    ADD CONSTRAINT batch_cmdline_key UNIQUE (cmdline);


--
-- Name: batch_job batch_job_batch_job_key; Type: CONSTRAINT; Schema: public; Owner: ft_view
--

ALTER TABLE ONLY public.batch_job
    ADD CONSTRAINT batch_job_batch_job_key UNIQUE (batch, job);


--
-- Name: job job_cmdline_key; Type: CONSTRAINT; Schema: public; Owner: ft_view
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT job_cmdline_key UNIQUE (cmdline);


--
-- Name: batch_cmdline_gin_jsonb_path_ops; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX batch_cmdline_gin_jsonb_path_ops ON public.batch USING gin (cmdline jsonb_path_ops);


--
-- Name: batch_cmdline_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX batch_cmdline_idx ON public.batch USING hash (cmdline);


--
-- Name: batch_created_at_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX batch_created_at_idx ON public.batch USING btree (created_at);


--
-- Name: batch_data_gin_jsonb_path_ops; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX batch_data_gin_jsonb_path_ops ON public.batch USING gin (data jsonb_path_ops);


--
-- Name: batch_job_batch_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX batch_job_batch_idx ON public.batch_job USING hash (batch);


--
-- Name: batch_job_job_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX batch_job_job_idx ON public.batch_job USING hash (job);


--
-- Name: batch_job_job_idx1; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX batch_job_job_idx1 ON public.batch_job USING hash (job);


--
-- Name: job_cmdline_gin_jsonb_path_ops; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX job_cmdline_gin_jsonb_path_ops ON public.job USING gin (cmdline jsonb_path_ops);


--
-- Name: job_cmdline_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX job_cmdline_idx ON public.job USING hash (cmdline);


--
-- Name: job_queue; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX job_queue ON public.job USING btree (((cmdline ->> 'env.MACHINERY'::text)) COLLATE "C", progress COLLATE "C");


--
-- Name: job_queue_; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX job_queue_ ON public.job USING btree (((cmdline ->> 'env.MACHINERY'::text)), progress text_pattern_ops);


--
-- Name: run_cleanup; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_cleanup ON public.run USING btree (run_started_at DESC);


--
-- Name: run_cmdline_gin_jsonb_path_ops; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_cmdline_gin_jsonb_path_ops ON public.run USING gin (run_cmdline jsonb_path_ops);


--
-- Name: run_history_filter_by_run_args; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_history_filter_by_run_args ON public.run USING btree (run_args, run_started_at DESC);


--
-- Name: run_history_filter_by_run_hostname; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_history_filter_by_run_hostname ON public.run USING btree (run_hostname, run_started_at DESC);


--
-- Name: run_history_filter_by_run_username; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_history_filter_by_run_username ON public.run USING btree (run_username, run_started_at DESC);


--
-- Name: run_history_filter_by_run_vms_url; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_history_filter_by_run_vms_url ON public.run USING btree (run_vms_url, run_started_at DESC);


--
-- Name: run_json__jsonb_path_ops; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_json__jsonb_path_ops ON public.run USING gin (run_json jsonb_path_ops);


--
-- Name: run_key; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE UNIQUE INDEX run_key ON public.run USING btree (run_username, run_hostname, run_started_at DESC, run_pid);


--
-- Name: run_message_trgm_index; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_message_trgm_index ON public.run USING gin (run_message public.gin_trgm_ops);


--
-- Name: run_run_args_run_started_at_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_run_args_run_started_at_idx ON public.run USING btree (run_args, run_started_at DESC);


--
-- Name: run_run_cmdline_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_run_cmdline_idx ON public.run USING hash (run_cmdline);


--
-- Name: run_run_index_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_run_index_idx ON public.run USING gin (run_index);


--
-- Name: run_run_username_run_vms_branch_run_vms_revision_run_ft_rev_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_run_username_run_vms_branch_run_vms_revision_run_ft_rev_idx ON public.run USING btree (run_username, run_vms_branch, run_vms_revision, run_ft_revision, run_started_at DESC);


--
-- Name: run_run_username_run_vms_branch_run_vms_revision_run_starte_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_run_username_run_vms_branch_run_vms_revision_run_starte_idx ON public.run USING btree (run_username, run_vms_branch, run_vms_revision, run_started_at DESC);


--
-- Name: run_run_vms_url_idx; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_run_vms_url_idx ON public.run USING btree (run_vms_url);


--
-- Name: run_ticket_trgm_index; Type: INDEX; Schema: public; Owner: ft_view
--

CREATE INDEX run_ticket_trgm_index ON public.run USING gin (run_ticket public.gin_trgm_ops);


--
-- Name: batch_job batch_job_batch_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ft_view
--

ALTER TABLE ONLY public.batch_job
    ADD CONSTRAINT batch_job_batch_fkey FOREIGN KEY (batch) REFERENCES public.batch(cmdline);


--
-- Name: batch_job batch_job_job_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ft_view
--

ALTER TABLE ONLY public.batch_job
    ADD CONSTRAINT batch_job_job_fkey FOREIGN KEY (job) REFERENCES public.job(cmdline);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: ft_view
--

REVOKE ALL ON SCHEMA public FROM postgres;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO ft_view;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- Name: TABLE batch; Type: ACL; Schema: public; Owner: ft_view
--

GRANT SELECT ON TABLE public.batch TO ft_view_read_only;


--
-- Name: TABLE batch_job; Type: ACL; Schema: public; Owner: ft_view
--

GRANT SELECT ON TABLE public.batch_job TO ft_view_read_only;


--
-- Name: TABLE job; Type: ACL; Schema: public; Owner: ft_view
--

GRANT SELECT ON TABLE public.job TO ft_view_read_only;


--
-- Name: TABLE run; Type: ACL; Schema: public; Owner: ft_view
--

GRANT SELECT ON TABLE public.run TO ft_view_read_only;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: ft_view
--

ALTER DEFAULT PRIVILEGES FOR ROLE ft_view IN SCHEMA public GRANT SELECT ON TABLES  TO ft_view_read_only;


--
-- PostgreSQL database dump complete
--

