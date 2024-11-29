# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
#!/usr/bin/env python3

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Mapping
from typing import Sequence

# pandas and numpy are not in requirements.txt,
# because they're very heavy but used only here.
# Add them to the pip command explicitly if needed.
import pandas as pd
from numpy import nan

from distrib import Version

_logger = logging.getLogger(__name__)


def _parse_duration(duration_s: float):
    return pd.Timedelta(float(duration_s), unit='sec').total_seconds()


def _search_key(root: Mapping, path: Sequence):
    for key in path:
        try:
            root = root[key]
        except KeyError:
            return nan
    return root


def _parse_timestamp(timestamp: str):
    return datetime.strptime(
        timestamp.rsplit('+')[0], '%Y-%m-%d %H:%M:%S.%f')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--input-dir',
        type=Path, default=Path(__file__).with_name('test_input'),
        help=(
            "JSON files with reports will be searched in this folder. It is "
            "assumed that filenames match to {branch}_test_results.json pattern."))
    parser.add_argument(
        '--tolerance', type=float, default=.1,
        help="Tolerance to results deviation between versions.")
    parser.add_argument(
        '--output-path', type=Path, default=Path(__file__).with_name('out.html'),
        help="Where to save output HTML file.",
        )
    parser.add_argument(
        '--dry-run', action='store_true',
        help="Don't collect any stats. Save text \"Test\" to output file and exit.")
    args = parser.parse_args()

    if args.dry_run:
        _logger.warning(
            "--dry-run flag passed to the script. No stats will be collected. Saving \"Test\" "
            "text to %s and exiting",
            args.output_path)
        args.output_path.write_text("<div>Test</div>")
        exit(0)
    path = args.input_dir
    col_name_2_report = []

    for file in Path(path).iterdir():
        if file.suffix != '.json':
            continue
        filename = file.name
        v = Version(filename[:filename.find('_test_results.json')])
        loaded = json.loads(open(file, 'r').read())
        col_name_2_report.append((v, loaded))

    col_name_2_report.sort(key=lambda v_2_rep: v_2_rep[0])

    col_names = [elem[0].__str__() for elem in col_name_2_report]
    reports = [elem[1] for elem in col_name_2_report]

    # Reference (stable) version against which comparisons are made
    ref_version = col_names[0]

    df = pd.DataFrame(reports, index=col_names).transpose()

    columns = pd.MultiIndex.from_product(
        [
            [c for c in df.columns],
            [
                'successful autodiscovery',
                'start_time',
                'duration, s',
                'end_time',
                'waited for stream, s',
                'full init time, s',
                'default bitrate, kbps',
                'rec bitrate, kbps',
                'stream params (best quality)',
                ],
            ],
        names=['version', 'parameter'],
        )

    df_res = pd.DataFrame(columns=columns)

    for row in df.iterrows():
        df_res.append(pd.Series(name=row[0], dtype='object'))
        for col in columns:
            stages = df.at[row[0], col[0]]
            if stages is nan:
                # Camera is not present in the report
                stages = {}
            if stages:
                successful_autodiscovery = _search_key(
                    stages, ['auto_discovery', 'is_success'])
                if not successful_autodiscovery:
                    _logger.info(
                        "No autodiscovery results for %s in %s. "
                        "Cannot calculate autodiscovery duration results.",
                        row[0], col[0])
                    successful_autodiscovery, start_time, duration, end_time = nan, nan, nan, nan
                else:
                    start_time = _search_key(stages, ['auto_discovery', 'start_time'])
                    end_time = _search_key(stages, ['auto_discovery', 'end_time'])
                    duration = _parse_duration(
                        _search_key(stages, ['auto_discovery', 'duration_s']))
                    start_time = _parse_timestamp(start_time)
                    end_time = _parse_timestamp(end_time)
                key_rec_off = ''
                key_rec_on = ''
                for stage_name in stages.keys():
                    if stage_name.startswith('stream_auto primary auto recording_off'):
                        key_rec_off = stage_name
                    if stage_name.startswith('stream_auto primary auto recording_on'):
                        key_rec_on = stage_name

                waited_for_stream = _search_key(
                    stages, [key_rec_off, 'raw_result', 'waited_for_stream_s', 'stream'])
                if pd.isna(waited_for_stream):
                    _logger.info(
                        f"No first frame waiting time found in report for {row[0]} in {col[0]}.")

                full_init_time = _parse_duration(
                    (_search_key(stages, [key_rec_off, 'raw_result', 'duration_sec', 'stream'])))
                if pd.isna(full_init_time):
                    _logger.info(
                        f"No stream init time results found in report for {row[0]} in {col[0]}.")

                default_bitrate = _search_key(
                    stages, [key_rec_off, 'raw_result', 'bitrate_kbps', 'stream'])
                if pd.isna(default_bitrate):
                    _logger.info(
                        f"No default bitrate results found in report for {row[0]} in {col[0]}.")

                result = _search_key(stages, [key_rec_on, 'raw_result'])
                if pd.isna(result):
                    rec_bitrate = nan
                    stream_params = nan
                    _logger.info(
                        f"No stream params found in report for {row[0]} in {col[0]}.")
                else:
                    rec_bitrate = _search_key(result, ['bitrate_kbps', 'stream'])
                    if pd.isna(rec_bitrate):
                        _logger.info(
                            f"No rec bitrate results found in report for {row[0]} in {col[0]}.")
                    res = _search_key(result, ['resolution', 'stream'])
                    if pd.isna(res):
                        stream_params = nan
                        _logger.info(
                            f"No stream params found in report for {row[0]} in {col[0]}.")
                    else:
                        if res.startswith('1x'):  # Get rid of '1x' preceding resolution value
                            res = res[2:]
                        stream_params = '{} {:.1f}fps {}'.format(
                            result['codec']['stream'],
                            result['actual_fps']['stream'],
                            res)
            else:
                _logger.info(
                    f"No results for stages found for {row[0]} in {col[0]}. Skipping it.")
                successful_autodiscovery = nan
                start_time = nan
                duration = nan
                end_time = nan
                waited_for_stream = nan
                full_init_time = nan
                default_bitrate = nan
                rec_bitrate = nan
                stream_params = nan

            df_res.loc[row[0], (col[0], 'successful autodiscovery')] = successful_autodiscovery
            df_res.loc[row[0], (col[0], 'start_time')] = start_time
            df_res.loc[row[0], (col[0], 'duration, s')] = duration
            df_res.loc[row[0], (col[0], 'end_time')] = end_time
            df_res.loc[row[0], (col[0], 'waited for stream, s')] = waited_for_stream
            df_res.loc[row[0], (col[0], 'full init time, s')] = full_init_time
            df_res.loc[row[0], (col[0], 'default bitrate, kbps')] = default_bitrate
            df_res.loc[row[0], (col[0], 'rec bitrate, kbps')] = rec_bitrate
            df_res.loc[row[0], (col[0], 'stream params (best quality)')] = stream_params

    df_res.append(pd.Series(name='Total autodiscovery duration, s', dtype='object'))

    for col in df_res.groupby(level='version', axis=1):
        min_start_time = pd.to_datetime(df_res[(col[0], 'start_time')]).min(skipna=True)
        max_end_time = pd.to_datetime(df_res[(col[0], 'end_time')]).max(skipna=True)
        duration = (max_end_time - min_start_time).total_seconds()
        df_res.at['Total autodiscovery duration, s', (col[0], 'duration, s')] = duration

    # Styling
    def highlight_difference(row, col, ref_v=ref_version, tolerance=args.tolerance):
        red = 'background-color: lightcoral'
        green = 'background-color: lightgreen'
        black = 'color: black'
        gray = 'background-color: lightgray'
        current = df_res.loc[row, col]
        if pd.isna(current):
            return black
        if current == "Failure":
            return gray
        ref = df_res.loc[row, (ref_v, col[1])]
        if isinstance(current, float):
            if current - ref > ref * tolerance:
                return red
            elif ref - current > ref * tolerance:
                if 'bitrate' in col[1]:
                    return red  # Any bitrate change is not desirable
                return green
            else:
                return black
        elif isinstance(current, bool):
            return red if not current else black
        return black

    # TODO: Get rid of highlight_difference, simplify style.apply
    s = (
        df_res.style
        .set_precision(1)
        .set_table_styles([
            {
                'selector': 'th, td', 'props': [
                    ('border-collapse', 'collapse'),
                    ('border-color', 'black'),
                    ('border-style', 'solid'),
                    ('border-width', '1px'),
                    ]},
            {
                'selector': 'td', 'props': [
                    ('text-align', 'right'),
                    ]},
            {
                'selector': 'tr:hover', 'props': [
                    ('background', '#e8edff'),  # noqa SpellCheckingInspection
                    ]},
            ])
        .apply(lambda y: pd.DataFrame(y).apply(
            lambda x: highlight_difference(x.name, y.name), axis=1))
        .hide_columns([
            col
            for col in df_res.columns
            if col[1] in ('start_time', 'end_time')
            ])
        .format(None, na_rep='--')
        )

    args.output_path.write_text(s.render())


if __name__ == '__main__':
    main()
