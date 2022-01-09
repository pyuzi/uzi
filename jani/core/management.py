




def execute_from_command_line(argv=None):
    """Run a ManagementUtility."""
    try:
        from django.core.management import ManagementUtility
    except ImportError as e:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            ) from e
    
        raise

    else:

        utility = ManagementUtility(argv)
        
        from jani.core import settings
        settings.IS_SETUP = utility.argv[0] not in {'runserver', 'shell'}

        utility.execute()
