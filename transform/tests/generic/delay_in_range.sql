{# Delays outside -60 .. 1440 minutes mean a parsing or time-zone bug. #}
{% test delay_in_range(model, column_name) %}
select * from {{ model }}
where {{ column_name }} < -60 or {{ column_name }} > 1440
{% endtest %}
