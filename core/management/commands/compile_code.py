from django.core.management.base import BaseCommand
from django.conf import settings
import os
import py_compile
from importlib import import_module
import python_minifier


class Command(BaseCommand):
    help = "Compiles python files in a directory"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apps_to_compile",
            default=[],
            type=str,
            help="Input of excel from which code needs to be generated.",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, **options):
        apps = (
            options["apps_to_compile"]
            if len(options["apps_to_compile"]) > 0
            else settings.SYSTEM_APPS + settings.BASE_APPS
        )
        for app_name in apps:
            module = import_module(app_name)
            if module:
                dirpath_or_none = (
                    module.__path__[0] if len(module.__path__) > 0 else None
                )
                for filename in os.listdir(dirpath_or_none):
                    file_path = os.path.join(dirpath_or_none, filename)
                    if filename.endswith(".py"):
                        try:
                            with open(file_path, "r+") as f:
                                minified_code = python_minifier.minify(source=f.read())
                                f.seek(0)
                                f.write(minified_code)
                                f.truncate()
                            py_compile.compile(file_path, doraise=True)
                            print(f"Compiled: {file_path}")
                        except Exception as e:
                            print(f"Error compiling {file_path}: {e}")
