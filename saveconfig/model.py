"""Project identity and fixed public sources for shared building blocks."""
from pathlib import Path
from . import VERSION
ROOT=Path(__file__).resolve().parent.parent
PROGRAM_ID='saveconfig'
PROJECT=dict(update_url='https://raw.githubusercontent.com/Lehner-007/saveconfig/main/github/version.json',source_url='https://raw.githubusercontent.com/Lehner-007/saveconfig/main/github/sprachpakete',deb={'package':'saveconfig'})
