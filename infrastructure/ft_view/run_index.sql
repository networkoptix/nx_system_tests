-- Store run metadata and message as one tsvector to allow for indexing,
-- and searching for error message and metadata. Hence the requirements:
-- - Punctuation is preserved;
-- - Numbers are replaced with placeholders.
--
-- Problem 1: Building tsvector and tsquery values
-- Postgres assumes searching human texts.
-- That is why tsvector and tsquery values are built by hand.
-- But they can only be built as a string representation and then parsing it.
-- Syntax is not standard! Both single quote and backslash are special.
-- The only way to quote an tsvector or tsquery element is array_to_tsvector().
-- quote_literal() may produce E'Foo\nBar', which is not supported here.
-- See: https://doxygen.postgresql.org/tsvector__parser_8c_source.html
--
-- Problem 2: More functions hurt performance: 3 vs 15 ms per 10k of message.
-- That is why some functions are inlined.

-- noinspection SqlResolveForFile @ routine/"array_to_tsvector"

-- Replace numbers, which often vary, with one token.
-- Ambiguity: hex numbers may also be words: 'face'.
-- If ambiguous, do replace. It rarely matters, but many matches is better than few.
-- It's possible to store something in the replacement: length, hex or dec, but
-- ambiguities arise: sizes or ports vary in length, hex number from dec digits.
CREATE OR REPLACE FUNCTION pg_temp.run_message_mask_numbers(word text) RETURNS text IMMUTABLE STRICT PARALLEL SAFE
RETURN regexp_replace(word, '^(?:0x)?[0-9a-fA-F]{2,}$|\d+', '###', 'g');

-- Tokenize a string.
-- Be granular. Trade performance for accuracy.
-- Split at the borders of double-click selection in a browser.
-- Additionally, split '\nFoo' -> '\' 'n' 'Foo' and '\xFF' -> '\' 'x' 'FF'.
CREATE OR REPLACE FUNCTION pg_temp.run_message_tokenize(message text) RETURNS setof text IMMUTABLE STRICT PARALLEL SAFE
BEGIN ATOMIC
SELECT m[1] FROM regexp_matches(message, '(?<=\\)\w|\w+|\S', 'g') AS m;
END;

CREATE OR REPLACE FUNCTION pg_temp.run_message_to_tsvector(message text) RETURNS tsvector IMMUTABLE PARALLEL SAFE
BEGIN ATOMIC
SELECT coalesce(string_agg(array_to_tsvector(ARRAY [pg_temp.run_message_mask_numbers(token)])::text || ':' || i, ' '), '')::tsvector
FROM pg_temp.run_message_tokenize(message) WITH ORDINALITY as _t(token, i);
END;

CREATE OR REPLACE FUNCTION pg_temp.run_message_to_tsquery(message text) RETURNS tsquery IMMUTABLE PARALLEL SAFE
BEGIN ATOMIC
SELECT coalesce(string_agg(array_to_tsvector(ARRAY [pg_temp.run_message_mask_numbers(token)])::text, ' <-> '), '')::tsquery
FROM pg_temp.run_message_tokenize(message) as _t(token);
END;

CREATE OR REPLACE FUNCTION pg_temp.run_metadata_to_tsvector(metadata jsonb) RETURNS tsvector IMMUTABLE PARALLEL SAFE
BEGIN ATOMIC
SELECT array_to_tsvector(coalesce(array_agg(key || '=' || value), ARRAY []::text[]))  -- No positions: treat them as tags.
FROM jsonb_each_text(metadata)
WHERE length(value) <= 1000;  -- tsvector element is limited to 2046.
END;

CREATE OR REPLACE FUNCTION pg_temp.run_metadata_to_tsquery(metadata jsonb) RETURNS tsquery IMMUTABLE PARALLEL SAFE
BEGIN ATOMIC
SELECT coalesce(string_agg(array_to_tsvector(ARRAY [key || '=' || value])::text, ' & '), '')::tsquery
FROM jsonb_each_text(metadata)
WHERE length(value) <= 1000;  -- tsvector element is limited to 2046.
END;

CREATE OR REPLACE FUNCTION pg_temp.run_to_tsvector(metadata jsonb, message text) RETURNS tsvector IMMUTABLE PARALLEL SAFE
RETURN pg_temp.run_metadata_to_tsvector(metadata) || pg_temp.run_message_to_tsvector(message);

CREATE OR REPLACE FUNCTION pg_temp.run_to_tsquery(metadata jsonb, message text) RETURNS tsquery IMMUTABLE PARALLEL SAFE
RETURN pg_temp.run_metadata_to_tsquery(metadata) && pg_temp.run_message_to_tsquery(message);
