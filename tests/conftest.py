import os

# Tests never call the live model (blueprint §18); .env loading does not override this.
os.environ["LLM_MODE"] = "fixture"
