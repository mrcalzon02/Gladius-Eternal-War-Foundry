"""Build the current officer with anatomical arms and native Guardsman gait."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_officer_arm_rebuild import main

if __name__ == "__main__":
    main()
