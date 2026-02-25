import os
import urllib.request
import zipfile
from pathlib import Path

from django.conf import settings


class DatabaseUpdateError(Exception):
    """Raised when the database update process fails."""


def update_database():
    """Download and replace the MTGJSON AllPrintings.sqlite database.

    Downloads the zip to a temp location, extracts AllPrintings.sqlite,
    verifies it, then swaps it into place — so the old DB is only removed
    after the new one is confirmed good.

    Raises DatabaseUpdateError on failure.
    """
    db_path = Path(settings.MTGJSON_DB_PATH)
    download_url = settings.MTGJSON_DOWNLOAD_URL
    zip_path = db_path.parent / 'AllPrintings.sqlite.zip'
    new_db_path = db_path.parent / 'AllPrintings.sqlite.new'
    old_db_path = db_path.parent / 'AllPrintings.sqlite.old'

    try:
        # Download zip (MTGJSON blocks default urllib User-Agent)
        req = urllib.request.Request(download_url)
        req.add_header('User-Agent', 'GatherThem/1.0')
        with urllib.request.urlopen(req) as resp, open(zip_path, 'wb') as out:
            while chunk := resp.read(1024 * 64):
                out.write(chunk)

        # Extract database from zip to a temp name
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            sqlite_files = [n for n in names if n.endswith('.sqlite')]
            if not sqlite_files:
                raise DatabaseUpdateError(
                    'No .sqlite file found in the downloaded archive.'
                )
            target_name = sqlite_files[0]
            zf.extract(target_name, db_path.parent)
            extracted = db_path.parent / target_name
            # Rename extracted file to .new temp name
            if extracted != new_db_path:
                if new_db_path.exists():
                    os.remove(new_db_path)
                extracted.rename(new_db_path)

        # Verify the new file exists and has content
        if not new_db_path.exists() or new_db_path.stat().st_size == 0:
            raise DatabaseUpdateError('Downloaded database is empty or missing.')

        # Atomic swap: old -> .old backup, new -> final
        if db_path.exists():
            if old_db_path.exists():
                os.remove(old_db_path)
            db_path.rename(old_db_path)

        new_db_path.rename(db_path)
        os.utime(db_path)

        # Clean up old backup
        if old_db_path.exists():
            os.remove(old_db_path)

    except DatabaseUpdateError:
        raise
    except Exception as e:
        raise DatabaseUpdateError(f'Failed to update database: {e}') from e
    finally:
        # Clean up temp files
        for temp in (zip_path, new_db_path):
            if temp.exists():
                os.remove(temp)
