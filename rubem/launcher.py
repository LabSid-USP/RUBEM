# From issue Pyinstaller a package with __main__.py
# https://github.com/pyinstaller/pyinstaller/issues/2560#issuecomment-777257579

from rubem.cli import * # noqa

if __name__ == "__main__":
    main() # noqa
