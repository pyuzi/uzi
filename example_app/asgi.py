"""
ASGI config for delete project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/howto/deployment/asgi/
"""

import os


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'example_app.settings')


from djx.core.asgi import get_asgi_application

application = get_asgi_application()