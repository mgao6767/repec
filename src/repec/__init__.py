import sys

if sys.version_info < (3, 10):
    raise RuntimeError("This package requires Python 3.10 or above.")
