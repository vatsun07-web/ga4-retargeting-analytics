# NB-01 | BigQuery SQL Documentation

**Project:** GA4 Google Merchandise Store — Marketing Propensity Model  
**Dataset:** `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`  
**Date range:** 2020-11-01 → 2021-01-31  
**Access method:** Manual CSV download from BigQuery console (no Python BigQuery library)

---

## Table of Contents

1. [Dataset Overview](#1-dataset-overview)
2. [Cost Control — Table Suffix Filter](#2-cost-control--table-suffix-filter)
3. [Schema Notes — Unnesting `event_params`](#3-schema-notes--unnesting-event_params)
4. [Query 1 — Sanity Check: Event Counts by Type](#4-query-1--sanity-check-event-counts-by-type)
5. [Query 2 — Session-Level Aggregation (Main Model Input)](#5-query-2--session-level-aggregation-main-model-input)
6. [Query 3 — Raw Event Sample with Unnested Params (Funnel / EDA Input)](#6-query-3--raw-event-sample-with-unnested-params-funnel--eda-input)
7. [Export Instructions](#7-export-instructions)
8. [Expected Output Files](#8-expected-output-files)
9. [Key Decisions](#9-key-decisions)

---

## 1. Dataset Overview

The GA4 obfuscated sample ecommerce dataset is a public BigQuery dataset provided by Google. It contains real GA4 event-level data from the Google Merchandise Store, with certain fields obfuscated (hashed user IDs, placeholder values such as `<Other>`, nulls in some geographic fields).

**Table structure:** One row per **event**, not per session or user.  
**Partitioning:** Sharded by date — one table per day, named `events_YYYYMMDD`.  
**Key complexity:** Most analytical fields are stored inside `event_params`, which is an `ARRAY<STRUCT<key STRING, value STRUCT<...>>>`. These must be unnested in SQL before export — pandas cannot parse this structure from raw BigQuery output.

### Key event names present in this dataset

| Event name | Meaning |
|---|---|
| `session_start` | A new session began |
| `page_view` | A page was viewed |
| `view_item` | A product detail page was viewed |
| `add_to_cart` | An item was added to the cart |
| `begin_checkout` | Checkout flow initiated |
| `purchase` | A transaction completed |

---

## 2. Cost Control — Table Suffix Filter

Every query in this project uses a `_TABLE_SUFFIX` filter to scan only the 92-day window needed. **Never run a query without this clause** — omitting it scans all available data and incurs unnecessary costs.

```sql
WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
```

BigQuery's wildcard table syntax (`events_*`) combined with `_TABLE_SUFFIX` enables partition pruning, so only the matching daily shards are scanned.

---

## 3. Schema Notes — Unnesting `event_params`

GA4 stores per-event parameters inside a repeated struct column: `event_params ARRAY<STRUCT<key STRING, value STRUCT<string_value STRING, int_value INT64, float_value FLOAT64, double_value FLOAT64>>>`.

To extract a single parameter, use a scalar subquery inside the `SELECT`:

```sql
-- Integer-valued parameter (e.g. ga_session_id, engagement_time_msec)
(SELECT ep.value.int_value
 FROM UNNEST(event_params) AS ep
 WHERE ep.key = 'ga_session_id')          AS session_id

-- String-valued parameter (e.g. page_location, medium, source)
(SELECT ep.value.string_value
 FROM UNNEST(event_params) AS ep
 WHERE ep.key = 'page_location')          AS page_location
```

**Why do this in SQL rather than Python?**  
Exporting the raw `event_params` column as CSV produces a nested string representation that is not reliably parseable by pandas. Unnesting in SQL outputs a clean, flat CSV that loads directly into a DataFrame with `pd.read_csv()`.

### Common parameters and their value types

| `ep.key` | Value field | Description |
|---|---|---|
| `ga_session_id` | `int_value` | Session identifier (scoped to user) |
| `ga_session_number` | `int_value` | Session count for this user |
| `page_location` | `string_value` | Full URL of the page |
| `page_title` | `string_value` | Page title |
| `source` | `string_value` | Traffic source (e.g. `google`) |
| `medium` | `string_value` | Traffic medium (e.g. `organic`, `cpc`) |
| `engagement_time_msec` | `int_value` | Engaged time in milliseconds |
| `session_engaged` | `string_value` | `'1'` if session was engaged |
| `transaction_id` | `string_value` | Purchase transaction ID |
| `value` | `float_value` | Purchase revenue value |

---

## 4. Query 1 — Sanity Check: Event Counts by Type

**Purpose:** Verify the dataset loaded correctly, understand event volume, and confirm all expected event types are present before running heavier queries.

**Run this first.** It is fast and cheap (aggregation only, no unnesting).

```sql
SELECT
    event_name,
    COUNT(*)                        AS event_count,
    COUNT(DISTINCT user_pseudo_id)  AS unique_users
FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
GROUP BY
    event_name
ORDER BY
    event_count DESC;
```

**Expected output shape:** ~15–25 rows (one per distinct event name).

**What to look for:**
- `page_view` and `session_start` should be among the highest-count events.
- `purchase` should be present with a much lower count — confirming the conversion rarity (~1–3% of sessions).
- Any unexpected event names (e.g. `scroll`, `click`, `video_start`) are noted here but not used in the model.

**Export:** Not needed — review results in the BigQuery console UI and note counts in NB-02 EDA.

---

## 5. Query 2 — Session-Level Aggregation (Main Model Input)

**Purpose:** Produce one row per session with all features needed for the propensity model. This is the primary export — saved as `data/raw/sessions.csv`.

**Logic summary:**
- Unit of analysis: `(user_pseudo_id, session_id)` — a unique session.
- Aggregation counts specific event types within each session.
- The `converted` flag is 1 if any `purchase` event occurred in the session.
- Session duration is derived from the min/max event timestamp within the session.
- Device, country, traffic source/medium are taken from any non-null row in the session (they are session-constant).

```sql
WITH session_events AS (
    SELECT
        user_pseudo_id,

        -- Extract session_id from event_params
        (SELECT ep.value.int_value
         FROM UNNEST(event_params) AS ep
         WHERE ep.key = 'ga_session_id')                        AS session_id,

        event_name,
        event_timestamp,

        -- Device and geo fields (session-level constants)
        device.category                                          AS device_category,
        geo.country                                              AS country,

        -- Traffic source fields
        traffic_source.medium                                    AS traffic_medium,
        traffic_source.source                                    AS traffic_source

    FROM
        `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
    WHERE
        _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
)

SELECT
    user_pseudo_id,
    session_id,

    -- Conversion label
    MAX(CASE WHEN event_name = 'purchase'       THEN 1 ELSE 0 END) AS converted,

    -- Event counts (features)
    COUNT(*)                                                         AS total_events,
    COUNTIF(event_name = 'page_view')                               AS page_views,
    COUNTIF(event_name = 'view_item')                               AS items_viewed,
    COUNTIF(event_name = 'add_to_cart')                             AS add_to_cart,
    COUNTIF(event_name = 'begin_checkout')                          AS checkout_starts,

    -- Session duration in seconds
    ROUND(
        (MAX(event_timestamp) - MIN(event_timestamp)) / 1000000.0,
        2
    )                                                                AS session_duration_sec,

    -- Session-level attributes (take any non-null value)
    MAX(device_category)                                             AS device,
    MAX(country)                                                     AS country,
    MAX(traffic_medium)                                              AS traffic_medium,
    MAX(traffic_source)                                              AS traffic_source

FROM
    session_events
WHERE
    session_id IS NOT NULL
GROUP BY
    user_pseudo_id,
    session_id
ORDER BY
    user_pseudo_id,
    session_id;
```

**Expected output shape:** ~130,000–160,000 rows × 13 columns.

**Expected conversion rate:** ~1–3% of rows will have `converted = 1`. Confirm this in NB-02 EDA.

**Export as:** `data/raw/sessions.csv`

### Column reference for `sessions.csv`

| Column | Type | Description |
|---|---|---|
| `user_pseudo_id` | STRING | Obfuscated user identifier |
| `session_id` | INT64 | Session identifier (scoped to user) |
| `converted` | INT64 | 1 = purchase occurred in session, 0 = no purchase |
| `total_events` | INT64 | Total event count in session |
| `page_views` | INT64 | Count of `page_view` events |
| `items_viewed` | INT64 | Count of `view_item` events |
| `add_to_cart` | INT64 | Count of `add_to_cart` events |
| `checkout_starts` | INT64 | Count of `begin_checkout` events |
| `session_duration_sec` | FLOAT64 | Duration from first to last event (seconds) |
| `device` | STRING | `desktop`, `mobile`, or `tablet` |
| `country` | STRING | User's country (may be NULL or `<Other>` for some rows) |
| `traffic_medium` | STRING | e.g. `organic`, `cpc`, `referral`, `(none)` |
| `traffic_source` | STRING | e.g. `google`, `(direct)`, `youtube.com` |

---

## 6. Query 3 — Raw Event Sample with Unnested Params (Funnel / EDA Input)

**Purpose:** Export a flat, row-per-event table for use in funnel analysis (NB-05) and EDA (NB-02). Includes unnested page location and engagement fields.

**Scope:** Limited to the six key funnel events to keep file size manageable. All 92 days are included.

```sql
SELECT
    user_pseudo_id,
    event_date,
    event_name,
    event_timestamp,

    -- Session identifier
    (SELECT ep.value.int_value
     FROM UNNEST(event_params) AS ep
     WHERE ep.key = 'ga_session_id')                            AS session_id,

    -- Page location (for funnel step identification)
    (SELECT ep.value.string_value
     FROM UNNEST(event_params) AS ep
     WHERE ep.key = 'page_location')                           AS page_location,

    -- Session engagement flag
    (SELECT ep.value.string_value
     FROM UNNEST(event_params) AS ep
     WHERE ep.key = 'session_engaged')                         AS session_engaged,

    -- Device and geo
    device.category                                             AS device_category,
    geo.country                                                 AS country,

    -- Traffic
    traffic_source.medium                                       AS traffic_medium

FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
    AND event_name IN (
        'session_start',
        'page_view',
        'view_item',
        'add_to_cart',
        'begin_checkout',
        'purchase'
    )
ORDER BY
    user_pseudo_id,
    event_timestamp;
```

**Expected output shape:** ~500,000–900,000 rows × 9 columns (varies — only funnel events included).

**Export as:** `data/raw/events_sample.csv`

### Column reference for `events_sample.csv`

| Column | Type | Description |
|---|---|---|
| `user_pseudo_id` | STRING | Obfuscated user identifier |
| `event_date` | STRING | Date string `YYYYMMDD` |
| `event_name` | STRING | One of the 6 funnel event types |
| `event_timestamp` | INT64 | Microseconds since Unix epoch |
| `session_id` | INT64 | Session identifier |
| `page_location` | STRING | Full page URL (may be NULL for non-pageview events) |
| `session_engaged` | STRING | `'1'` if engaged session, else NULL |
| `device_category` | STRING | `desktop`, `mobile`, or `tablet` |
| `country` | STRING | User's country |
| `traffic_medium` | STRING | Traffic medium |

---

## 7. Export Instructions

Run each query in the BigQuery console, then export the results as CSV.

### Steps (BigQuery console UI)

1. Open [console.cloud.google.com/bigquery](https://console.cloud.google.com/bigquery)
2. Paste the query into the editor
3. Click **Run** — verify row count and preview matches expectations
4. Click **Save Results → CSV (local file)**
5. Save to the correct path in your local `data/raw/` folder

### Query order

| Order | Query | Save as |
|---|---|---|
| 1 | Sanity check (review in UI only) | — |
| 2 | Session-level aggregation | `data/raw/sessions.csv` |
| 3 | Raw event sample | `data/raw/events_sample.csv` |

> **Note:** Run the sanity check first and verify `purchase` events exist before running the heavier queries. This confirms the date range and dataset are correct.

---

## 8. Expected Output Files

```
data/
└── raw/
    ├── sessions.csv          # ~130K–160K rows, 13 cols — model input
    └── events_sample.csv     # ~500K–900K rows, 10 cols — EDA / funnel input
```

Both files are listed in `.gitignore` and must never be committed to GitHub.

---

## 9. Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| BigQuery access method | Manual CSV download from console | Avoids installing `google-cloud-bigquery`; simpler setup for portfolio |
| Unnesting strategy | SQL scalar subqueries | GA4 `ARRAY<STRUCT>` is not cleanly parseable from raw CSV in pandas |
| Session duration method | `(MAX(timestamp) - MIN(timestamp)) / 1e6` | Converts microseconds to seconds; handles single-event sessions (duration = 0) |
| Session-level attributes | `MAX()` aggregation | Device/country/medium are session-constant; `MAX` picks the non-null value |
| Event filter for events_sample | 6 funnel events only | Limits file size; non-funnel events (scroll, click) not needed for NB-02 or NB-05 |
| Cost control | `_TABLE_SUFFIX BETWEEN` on every query | Prevents accidental full-dataset scans |
| `session_id IS NOT NULL` filter | Applied in Query 2 WHERE clause | Drops rare rows where `ga_session_id` param is missing; avoids NULL key in GROUP BY |

---

*NB-01 complete. Proceed to NB-02 EDA once both CSV files are downloaded and placed in `data/raw/`.*
