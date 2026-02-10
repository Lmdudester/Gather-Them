import threading

from django.http import HttpResponse
from django.template.loader import render_to_string

_maintenance_lock = threading.Lock()
_maintenance_mode = False


def set_maintenance_mode(enabled):
    global _maintenance_mode
    with _maintenance_lock:
        _maintenance_mode = enabled


def is_maintenance_mode():
    with _maintenance_lock:
        return _maintenance_mode


class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_maintenance_mode() and request.path != '/update-db/':
            html = render_to_string('finder/maintenance.html', request=request)
            return HttpResponse(html, status=503)
        return self.get_response(request)
