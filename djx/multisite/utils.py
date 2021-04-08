import inspect

from django.apps import apps

from threading import local

_thread_locals = local()


def get_model_by_db_table(db_table):
    for model in apps.get_models():
        if model._meta.db_table == db_table:
            return model
    else:
        # here you can do fallback logic if no model with db_table found
        raise ValueError('No model found with db_table {}!'.format(db_table))
        # or return None


def get_current_site():
    """
    Utils to get the site that hass been set in the current thread using `set_current_site`.
    Can be used by doing:
    ```
        my_class_object = get_current_site()
    ```
    Will return None if the site is not set
    """
    return getattr(_thread_locals, 'site', None)


def get_site_column(model_class_or_instance):
    if inspect.isclass(model_class_or_instance):
        model_class_or_instance = model_class_or_instance()

    try:
        return model_class_or_instance.site_field
    except:
        raise ValueError('''%s is not an instance or a subclass of SiteModel
                         or does not inherit from SiteMixin'''
                         % model_class_or_instance.__class__.__name__)


def get_site_field(model_class_or_instance):
    site_column = get_site_column(model_class_or_instance)
    all_fields = model_class_or_instance._meta.fields
    try:
        return next(field for field in all_fields if field.column == site_column)
    except StopIteration:
        raise ValueError('No field found in {} with column name "{}"'.format(
                         model_class_or_instance, site_column))


def get_object_site(instance):
    field = get_site_field(instance)

    if field.primary_key:
        return instance

    return getattr(instance, field.name, None)


def set_object_site(instance, value):
    if instance.site_value is None and value and not isinstance(value, list):
        setattr(instance, instance.site_field, value)


def get_current_site_value():
    current_site = get_current_site()
    if not current_site:
        return None

    try:
        current_site = list(current_site)
    except TypeError:
        return current_site.site_value

    values = []
    for t in current_site:
        values.append(t.site_value)
    return values


def get_site_filters(table, filters=None):
    filters = filters or {}

    current_site_value = get_current_site_value()

    if not current_site_value:
        return filters

    if isinstance(current_site_value, list):
        filters['%s__in' % get_site_column(table)] = current_site_value
    else:
        filters[get_site_column(table)] = current_site_value

    return filters


def set_current_site(site):
    """
    Utils to set a site in the current thread.
    Often used in a middleware once a user is logged in to make sure all db
    calls are sharded to the current site.
    Can be used by doing:
    ```
        get_current_site(my_class_object)
    ```
    """

    setattr(_thread_locals, 'site', site)


def unset_current_site():
    setattr(_thread_locals, 'site', None)


def is_distributed_model(model):
    try:
        get_site_field(model)
        return True
    except ValueError:
        return False
