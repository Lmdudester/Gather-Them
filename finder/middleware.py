import json
import os
import time
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string

_STALE_LOCK_SECONDS = 30 * 60  # 30 minutes


def _lock_file_path():
    if not settings.MTGJSON_DB_PATH:
        return None
    return Path(settings.MTGJSON_DB_PATH).parent / '.maintenance_lock'


def _result_file_path():
    if not settings.MTGJSON_DB_PATH:
        return None
    return Path(settings.MTGJSON_DB_PATH).parent / '.update_result'


def enter_maintenance_mode():
    """Atomically create the lock file. Returns True on success, False if already locked."""
    path = _lock_file_path()
    if path is None:
        return False

    # Check for stale lock (e.g. left behind after a crash).
    # The remove-then-create sequence is not atomic: two processes may both
    # detect the stale lock and race to remove it.  That is fine — the
    # subsequent O_CREAT|O_EXCL is the single point of serialisation.
    try:
        if path.exists():
            age = time.time() - path.stat().st_mtime
            if age > _STALE_LOCK_SECONDS:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass  # another process already removed the stale lock
    except OSError:
        pass

    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except (FileExistsError, OSError):
        return False


def exit_maintenance_mode():
    """Remove the lock file."""
    path = _lock_file_path()
    if path is None:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def set_maintenance_mode(enabled):
    """Enter or exit maintenance mode based on a boolean flag."""
    if enabled:
        enter_maintenance_mode()
    else:
        exit_maintenance_mode()


def is_maintenance_mode():
    """Check whether maintenance mode is active."""
    path = _lock_file_path()
    if path is None:
        return False
    return path.exists()


def set_update_result(level, message):
    """Write an update result to the result file as JSON."""
    path = _result_file_path()
    if path is None:
        return
    path.write_text(json.dumps({'level': level, 'message': message}))


def pop_update_result():
    """Read and delete the result file. Returns (level, message) or None."""
    path = _result_file_path()
    if path is None:
        return None
    try:
        data = json.loads(path.read_text())
        os.remove(path)
        return (data['level'], data['message'])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


_MAINTENANCE_ALLOWED_PATHS = {'/update-db/', '/api/random-flavor/'}


class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_maintenance_mode() and request.path not in _MAINTENANCE_ALLOWED_PATHS:
            html = render_to_string('finder/maintenance.html', request=request)
            return HttpResponse(html, status=503)

        response = self.get_response(request)

        # Flash any pending update result — must run AFTER get_response()
        # so that SessionMiddleware/MessageMiddleware have processed the request.
        result = pop_update_result()
        if result:
            from django.contrib import messages
            level_map = {'success': messages.SUCCESS, 'error': messages.ERROR}
            messages.add_message(request, level_map.get(result[0], messages.INFO), result[1])

        return response
