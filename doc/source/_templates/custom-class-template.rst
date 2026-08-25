{{ fullname | escape | underline}}

.. currentmodule:: {{ module }}

.. autoclass:: {{ objname }}
   :members:
   :show-inheritance:
   :inherited-members: BaseModel
   :special-members: __call__, __add__, __mul__

   {# Members inherited from pydantic.BaseModel are not part of the RUBEM API. #}
   {% set pydantic_members = [
      'construct', 'copy', 'dict', 'from_orm', 'json', 'parse_file', 'parse_obj',
      'parse_raw', 'schema', 'schema_json', 'update_forward_refs', 'validate',
   ] %}
   {% block methods %}
   {% if methods %}
   .. rubric:: {{ _('Methods') }}

   .. autosummary::
      :nosignatures:
   {% for item in methods %}
      {%- if not item.startswith('_') and not item.startswith('model_') and item not in pydantic_members %}
      ~{{ name }}.{{ item }}
      {%- endif -%}
   {%- endfor %}
   {% endif %}
   {% endblock %}

   {% block attributes %}
   {% if attributes %}
   .. rubric:: {{ _('Attributes') }}

   .. autosummary::
   {% for item in attributes %}
      {%- if not item.startswith('model_') %}
      ~{{ name }}.{{ item }}
      {%- endif -%}
   {%- endfor %}
   {% endif %}
   {% endblock %}
