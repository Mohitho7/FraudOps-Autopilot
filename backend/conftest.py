"""
Global pytest configuration and sys.path setup.
"""

from pathlib import Path
import sys

# Ensure backend root is in python path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
