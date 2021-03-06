try:
    import simplejson as json
except ImportError:
    import json

import dateutil.parser
from collections import namedtuple
from .utils import unicode_class, resource_for_link, unresolvable
from .resource import FieldsResource

"""
contentful.content_type_field_types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module implements the Field Coercion classes.

:copyright: (c) 2016 by Contentful GmbH.
:license: MIT, see LICENSE for more details.
"""


class BasicField(object):
    """Base Coercion Class"""

    def __init__(self, items=None):
        self._items = items

    def coerce(self, value, **kwargs):
        """Just returns the value."""

        return value

    def __repr__(self):
        return "<{0}>".format(
            self.__class__.__name__
        )


class SymbolField(BasicField):
    """Symbol Coercion Class"""

    def coerce(self, value, **kwargs):
        """Coerces value to str"""

        return unicode_class()(value)


class TextField(BasicField):
    """Text Coercion Class"""

    def coerce(self, value, **kwargs):
        """Coerces value to str"""

        return unicode_class()(value)


class IntegerField(BasicField):
    """Integer Coercion Class"""

    def coerce(self, value, **kwargs):
        """Coerces value to int"""

        return int(value)


class NumberField(BasicField):
    """Number Coercion Class"""

    def coerce(self, value, **kwargs):
        """Coerces value to float"""

        return float(value)


class DateField(BasicField):
    """Date Coercion Class"""

    def coerce(self, value, **kwargs):
        """Coerces ISO8601 date to :class:`datetime.datetime` object."""

        return dateutil.parser.parse(value)


class BooleanField(BasicField):
    """Boolean Coercion Class"""

    def coerce(self, value, **kwargs):
        """Coerces value to boolean"""

        return bool(value)


class LocationField(BasicField):
    """Location Coercion Class"""

    def coerce(self, value, **kwargs):
        """Coerces value to Location object"""

        Location = namedtuple('Location', ['lat', 'lon'])
        return Location(float(value.get('lat')), float(value.get('lon')))


class LinkField(BasicField):
    """
    LinkField

    Nothing should be done here as include resolution is handled within
    entries due to depth handling (explained within Entry).
    Only present as a placeholder for proper resolution within ContentType.
    """
    pass


class ArrayField(BasicField):
    """Array Coercion Class

    Coerces items in collection with it's proper Coercion Class.
    """

    def __init__(self, items=None):
        super(ArrayField, self).__init__(items)
        self._coercion = self._get_coercion()

    def coerce(self, value, **kwargs):
        """Coerces array items with proper coercion."""

        result = []
        for v in value:
            result.append(self._coercion.coerce(v, **kwargs))
        return result

    def _get_coercion(self):
        return globals()["{0}Field".format(self._items.get('type'))]()


class ObjectField(BasicField):
    """
    Object Coercion Class.
    """

    def coerce(self, value, **kwargs):
        """Coerces JSON values properly."""

        return json.loads(json.dumps(value))


class StructuredTextField(BasicField):
    """
    Coerces Structured Text fields and resolves includes for entries included.
    """

    def _coerce_link(self, value, includes=None, errors=None, resources=None, default_locale='en-US', locale=None):
        if 'data' not in value or 'target' not in value['data']:
            return value

        if not('target' in value['data'] and value['data']['target']['sys']['type'] == 'Link'):
            return value

        if unresolvable(value['data']['target'], errors):
            return None

        resource = resource_for_link(
            value['data']['target'],
            includes,
            resources,
            locale=locale if locale else '*'
        )

        if isinstance(resource, FieldsResource):  # Resource comes from instance cache
            return resource

        from .resource_builder import ResourceBuilder
        return ResourceBuilder(
            default_locale,
            locale and locale == '*',
            resource,
            includes,
            reuse_entries=bool(resources),
            resources=resources
        ).build()

    def _coerce_block(self, value, includes=None, errors=None, resources=None, default_locale='en-US', locale=None):
        if not (isinstance(value, dict) and 'content' in value):
            return value

        invalid_nodes = []
        for index, node in enumerate(value['content']):
            if node['nodeClass'] == 'block' and 'data' in node:
                link = self._coerce_link(
                    node,
                    includes=includes,
                    errors=errors,
                    resources=resources,
                    default_locale=default_locale,
                    locale=locale
                )
                if link:
                    node['data'] = link
                else:
                    invalid_nodes.append(index)
            elif node['nodeClass'] == 'block' and 'content' in node:
                node['content'] = self._coerce_block(
                    node,
                    includes=includes,
                    errors=errors,
                    resources=resources,
                    default_locale=default_locale,
                    locale=locale
                )

        for node_index in invalid_nodes:
            del value['content'][node_index]

        return value

    def coerce(self, value, includes=None, errors=None, resources=None, default_locale='en-US', locale=None):
        """Coerces Structured Text properly."""

        return self._coerce_block(
            value,
            includes=includes,
            errors=errors,
            resources=resources,
            default_locale=default_locale,
            locale=locale
        )
