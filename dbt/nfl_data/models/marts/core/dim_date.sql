-- models/dim_date.sql
-- This model compiles different SQL depending on the adapter (duckdb vs snowflake).

{% if target.type == 'duckdb' %}

WITH date_spine AS (
    SELECT
        generate_series::DATE AS date_day
    FROM generate_series(
        DATE '1999-01-01',
        DATE '2035-12-31',
        INTERVAL 1 DAY
    )
),
final AS (
    SELECT
        date_day AS date,
        CAST(strftime(date_day, '%Y%m%d') AS BIGINT) AS date_key,
        CAST(strftime(date_day, '%Y') AS INTEGER) AS year,
        CAST(((CAST(strftime(date_day, '%m') AS INTEGER) - 1) / 3) + 1 AS INTEGER) AS quarter,
        CAST(strftime(date_day, '%m') AS INTEGER) AS month,
        strftime(date_day, '%B') AS month_name,
        CAST(strftime(date_day, '%d') AS INTEGER) AS day,
        CAST(strftime(date_day, '%w') AS INTEGER) AS day_of_week_num,  -- 0=Sunday..6=Saturday
        strftime(date_day, '%A') AS day_of_week_name,
        CAST(strftime(date_day, '%W') AS INTEGER) AS week_of_year
    FROM date_spine
)
SELECT
    final.date,
    final.date_key,
    final.year,
    final.quarter,
    final.month,
    final.month_name,
    final.day,
    final.day_of_week_num,
    final.day_of_week_name,
    final.week_of_year
FROM final


{% elif target.type == 'snowflake' %}

WITH date_spine AS (
    SELECT
        DATEADD(DAY, SEQ4(), TO_DATE('1999-01-01')) AS date_day
    FROM TABLE(GENERATOR(ROWCOUNT => 13500))
),
final AS (
    SELECT
        date_day AS date,
        TO_NUMBER(TO_CHAR(date_day, 'YYYYMMDD')) AS date_key,
        YEAR(date_day) AS year,
        QUARTER(date_day) AS quarter,
        MONTH(date_day) AS month,
        TO_CHAR(date_day, 'MMMM') AS month_name,
        DAY(date_day) AS day,
        DAYOFWEEK(date_day) AS day_of_week_num,      -- 1=Sunday..7=Saturday
        TO_CHAR(date_day, 'DY') AS day_of_week_name, -- MON/TUE...
        WEEKOFYEAR(date_day) AS week_of_year
    FROM date_spine
    WHERE date_day <= TO_DATE('2035-12-31')
)
SELECT
    final.date,
    final.date_key,
    final.year,
    final.quarter,
    final.month,
    final.month_name,
    final.day,
    final.day_of_week_num,
    final.day_of_week_name,
    final.week_of_year
FROM final


{% else %}

{{ exceptions.raise_compiler_error("dim_date.sql does not support adapter type: " ~ target.type) }}

{% endif %}
