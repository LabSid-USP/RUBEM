import os
import sys

try:
    from rubem.cli import main
except ModuleNotFoundError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
    from rubem.cli import main

if __name__ == "__main__":
    main()
