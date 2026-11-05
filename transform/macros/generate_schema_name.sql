{# Models land exactly in intermediate / marts / ml, not "intermediate_marts". #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ (custom_schema_name or target.schema) | trim }}
{%- endmacro %}
