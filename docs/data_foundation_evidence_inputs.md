# Data-Foundation Evidence Inputs

This guide maps external evidence templates to the ignored accepted input paths and validator commands for the active h5 / 5d research pipeline.

The templates are non-evidence. CSV templates are header-only and must not include example evidence rows. Accepted inputs must come from authoritative external sources, and schema validation only checks intake structure. It does not prove production readiness, live-trading readiness, profitability, option liquidity, option P&L, or investment advice.

PIT means point-in-time: metadata valid as of the prediction date, not a future-resolved view. PIT evidence must not rely on future-resolved ticker status, delisting outcomes, template rows, or ticker-list inference.

## PIT Security Master

- Template: `docs/examples/pit_security_master_template.csv`
- Accepted input: `data/reference/pit_security_master.csv`
- Validator: `python scripts/validation/audit_pit_security_master_inventory.py`
- Evidence caveat: use only a licensed CRSP/WRDS-style export or equivalent authoritative PIT source. Do not populate this from OHLCV ticker lists, template rows, or ticker-string inference.

## Corporate Actions

- Template: `docs/examples/corporate_actions_template.csv`
- Accepted input: `data/reference/corporate_actions.csv`
- Validator: `python scripts/validation/audit_corporate_action_inventory.py`
- Evidence caveat: event rows can support corporate-action review, but they do not by themselves prove OHLCV adjusted/unadjusted policy.

## OHLCV Adjustment Policy

- Template: `docs/examples/ohlcv_adjustment_policy_template.json`
- Accepted input: `data/reference/ohlcv_adjustment_policy.json`
- Validator: `python scripts/validation/audit_corporate_action_inventory.py`
- Evidence caveat: use official source documentation only. Empty template values remain non-evidence and must not clear the adjustment-policy blocker.

## Alpha Vantage Listing Status (Supplemental Only)

- Template: `docs/examples/alpha_vantage_listing_status_template.csv`
- Accepted input: `data/reference/alpha_vantage_listing_status.csv`
- Downloader: `python scripts/phase1A_download/download_alpha_vantage_listing_status.py`
- Evidence caveat: Alpha Vantage LISTING_STATUS can provide active/delisted US stock and ETF lifecycle rows after 2010-01-01, but it is supplemental survivorship evidence only. It must not populate or clear `data/reference/pit_security_master.csv` because it does not prove permanent security IDs, full ticker-history intervals, or security-class flags required for CRSP/WRDS-style PIT clearance.
