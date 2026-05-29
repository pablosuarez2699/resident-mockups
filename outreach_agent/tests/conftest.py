import os
import sys

# Make the agent package importable (modules use top-level imports like `import config`)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
