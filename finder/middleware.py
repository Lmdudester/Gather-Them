import threading

from django.http import HttpResponse
from django.template.loader import render_to_string

_maintenance_lock = threading.Lock()
_maintenance_mode = False
_update_result = None  # ('success', msg) or ('error', msg), consumed on next request


def set_maintenance_mode(enabled):
    global _maintenance_mode
    with _maintenance_lock:
        _maintenance_mode = enabled


def is_maintenance_mode():
    with _maintenance_lock:
        return _maintenance_mode


def set_update_result(level, message):
    global _update_result
    with _maintenance_lock:
        _update_result = (level, message)


def pop_update_result():
    global _update_result
    with _maintenance_lock:
        result = _update_result
        _update_result = None
        return result


class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_maintenance_mode() and request.path != '/update-db/':
            html = render_to_string('finder/maintenance.html', request=request)
            return HttpResponse(html, status=503)

        # Flash any pending update result onto this request
        result = pop_update_result()
        if result:
            from django.contrib import messages
            level_map = {'success': messages.SUCCESS, 'error': messages.ERROR}
            messages.add_message(request, level_map.get(result[0], messages.INFO), result[1])

        return self.get_response(request)
