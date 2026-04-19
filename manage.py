#!/usr/bin/env python
import os
import sys


def _prepend_osgeo4w_bin_to_path() -> None:
    """Help GeoDjango find GDAL/GEOS when OSGeo4W is installed on Windows."""
    if sys.platform != "win32":
        return
    roots = [
        os.environ.get("OSGEO4W_ROOT"),
        r"C:\OSGeo4W64",
        r"C:\OSGeo4W",
    ]
    for root in roots:
        if not root:
            continue
        bin_dir = os.path.join(root, "bin")
        if os.path.isdir(bin_dir):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            return


def _ensure_local_dev_allowed_hosts() -> None:
    """Expo phones use Host: <LAN-IP>:8000; .env often sets DJANGO_ALLOWED_HOSTS=localhost → DisallowedHost."""
    mod = os.environ.get("DJANGO_SETTINGS_MODULE") or "config.settings.local"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", mod)
    if not str(mod).endswith(".local"):
        return
    if os.environ.get("DJANGO_STRICT_ALLOWED_HOSTS", "").lower() in ("1", "true", "yes"):
        return
    os.environ["DJANGO_ALLOWED_HOSTS"] = "*"


def main() -> None:
    _prepend_osgeo4w_bin_to_path()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "config.settings.local"))
    _ensure_local_dev_allowed_hosts()
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
