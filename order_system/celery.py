"""
Celery configuration for background task processing
Handles async SMS and email notifications
"""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'order_system.settings')

app = Celery('order_system')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """
    Bound Celery debug task used to verify Celery is configured and running.
    
    When called (in development), it prints the current task request object — useful for inspecting the executing task's metadata (id, args, kwargs). Not intended for production use.
    """
    print(f'Request: {self.request!r}')