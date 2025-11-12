"""
WSGI config for edu_score project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edu_score.settings')

application = get_wsgi_application()
app = application 
