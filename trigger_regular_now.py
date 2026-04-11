import os

os.environ["FORCE_REGULAR_NOW"] = "true"
os.environ.setdefault("DRY_RUN", "false")

import main_master_v3

main_master_v3.main()
