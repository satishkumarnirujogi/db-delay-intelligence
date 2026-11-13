{# Minutes of delay for an interval, clamped to the range the delay_in_range test allows (-60 .. 1440).
   DB sometimes reports impossible times, e.g. a train leaving 61 min early. NULL stays NULL
   (greatest/least alone would turn a missing arrival into -60). #}
{% macro plausible_delay(interval_expr) %}
{%- set m = "round(extract(epoch from (" ~ interval_expr ~ ")) / 60)::int" -%}
case when {{ m }} is not null then greatest(-60, least(1440, {{ m }})) end
{%- endmacro %}
