# Stage 17 Manual Option-Chain Mapping

Use `docs/examples/stage17_manual_option_chain_template.csv` as the canonical manual worksheet for preparing a broker or vendor option-chain export before Stage 17 import. This is for Stage 16 h5 underlying candidate review and data collection only. It is not a trade recommendation, not proof of option liquidity, and not an option P&L test.

## Fill The Template

- `snapshot_date`: date the option chain was captured, in `YYYY-MM-DD`.
- `snapshot_time`: capture time if available; leave blank if the export has only a date.
- `underlying`: underlying ticker, such as `AAPL`.
- `expiration`: option expiration date, in `YYYY-MM-DD`.
- `dte`: days to expiration if provided; Stage 17 can compute this from `snapshot_date` and `expiration` after mapping.
- `option_type`: call/put marker. Accepted values are `C`, `P`, `CALL`, or `PUT`.
- `strike`, `bid`, `ask`: required numeric contract and quote fields.
- `mid`: optional; Stage 17 can compute `(bid + ask) / 2` after mapping.
- `last`, `volume`, `open_interest`, `implied_volatility`, `delta`, `gamma`, `theta`, `vega`: optional; leave blank if the source does not provide them.
- `source`: vendor, broker, or manual source name.
- `source_symbol`: option contract symbol from the source export, if available.

## Required Core Fields

Before Stage 17 import, each row must have `snapshot_date`, `underlying`, `expiration`, `option_type`, `strike`, `bid`, `ask`, `source`, and `source_symbol`. Missing core fields should stop the import preparation.

## Stage 17 Field Mapping

Stage 17 currently imports the internal schema, so a manual export must be renamed or converted before import:

| Template column | Stage 17 import column |
| --- | --- |
| `snapshot_date` | `snapshot_date` |
| `snapshot_time` | `snapshot_timestamp` |
| `underlying` | `underlying_ticker` |
| `expiration` | `expiration` |
| `dte` | `DTE` |
| `option_type` | `call_put` |
| `strike` | `strike` |
| `bid` | `bid` |
| `ask` | `ask` |
| `mid` | `mid` |
| `last` | `last` |
| `volume` | `volume` |
| `open_interest` | `open_interest` |
| `implied_volatility` | `implied_volatility` |
| `delta` | `delta` |
| `gamma` | `gamma` |
| `theta` | `theta` |
| `vega` | `vega` |
| `source` | `data_source` |
| `source_symbol` | `option_symbol` |

Optional Stage 17 fields not present in this template, such as `underlying_price`, `data_delay_status`, and `quote_timestamp`, may be left absent or null if the manual source does not provide them.

## Batch Manifest

Store manually captured option-chain CSV files under `manual_option_snapshots/`, not under `data/raw_txt` or other raw stock-data folders. Use names like `<TICKER>_<YYYY-MM-DD>_<source>_option_chain.csv`.

Use `docs/examples/stage17_manual_snapshot_manifest_template.csv` for repeatable batch imports. The manifest columns are:

| Manifest column | Meaning |
| --- | --- |
| `file_path` | Repo-relative or absolute path to the manual option-chain CSV. |
| `underlying` | One underlying ticker expected in the CSV. |
| `snapshot_date` | Snapshot date expected in the CSV. |
| `snapshot_time` | Optional snapshot time expected in the CSV. |
| `source` | Source expected in the CSV. |
| `notes` | Free-text review notes. |

Batch import preserves the same Stage 17 internal schema as single-file import. It writes per-file raw, normalized, candidate-linked, and summary outputs, plus:

- `reports/options/stage17_manual_snapshot_batch_summary.json`
- `reports/options/stage17_manual_snapshot_candidate_coverage.csv`
- `reports/options/stage17_manual_snapshot_batch_failures.csv`

The candidate coverage report is one row per Stage 16 h5 daily underlying candidate. It includes snapshot counts, contract row counts, snapshot dates, latest snapshot date, `snapshot_matches_score_date_any`, and `options_liquidity_verified=false`.

## Validation Rules

- `bid`, `ask`, and `strike` must be nonnegative.
- `bid` must be less than or equal to `ask`.
- `volume` and `open_interest`, when present, must be nonnegative.
- `expiration` should be after `snapshot_date`.
- Imported rows link to Stage 16 candidates by ticker only. Keep `snapshot_date` separate from Stage 16 `score_date`; do not imply the chain existed on the score date unless the dates match.
- Rows importing successfully do not prove option liquidity, execution quality, IV/Greek quality, trade suitability, or option profitability.
- `options_liquidity_verified` must remain `false` until explicit option liquidity criteria are defined and tested later.
