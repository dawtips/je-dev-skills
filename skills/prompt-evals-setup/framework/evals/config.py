"""Configuration surface for the prompt evaluation framework.

Edit these constants to point the framework at your provider/models and to set
your application's pass bar. Everything here has a sensible default.
"""

# --- Provider / models -------------------------------------------------------
# Provider is currently "anthropic". To swap providers, implement the LLMClient
# protocol in evals/evaluator/client.py and pass your client into PromptEvaluator.
PROVIDER = "anthropic"

# Model that GENERATES the dataset (ideas + test cases).
GENERATOR_MODEL = "claude-sonnet-4-6"

# Default model for the prompt/agent UNDER TEST (your run_function may override).
EXECUTOR_MODEL = "claude-haiku-4-5-20251001"

# Judge model. Deliberately a STRONG model, and ideally different from the
# executor to reduce self-grading bias (see spec Â§Known Limitations).
JUDGE_MODEL = "claude-opus-4-8"

# Environment variable the Anthropic client reads the API key from.
API_KEY_ENV = "ANTHROPIC_API_KEY"

# Max output tokens per framework LLM call (generation + grading).
MAX_TOKENS = 2048

# --- Temperatures (see spec Â§Recommended model settings) ---------------------
# Applied only to models that accept sampling params. Claude Opus 4.7+ removed
# temperature/top_p/top_k (sending them 400s), so the reference client omits it
# for those models — see evaluator/client.py. With the default JUDGE_MODEL
# (Opus 4.8) GRADING_TEMPERATURE is therefore ignored; pick a Sonnet/Haiku judge
# if you need an explicit grading temperature.
IDEA_TEMPERATURE = 1.0      # maximize scenario diversity
TESTCASE_TEMPERATURE = 0.7  # realistic but varied
GRADING_TEMPERATURE = 0.0   # deterministic, reproducible scores

# --- Concurrency -------------------------------------------------------------
MAX_CONCURRENT_TASKS = 3    # worker-pool width; trade speed vs. rate limits

# --- Scoring / reporting -----------------------------------------------------
PASS_THRESHOLD = 7          # a case "passes" if score >= this
COLOR_GREEN_MIN = 8         # HTML report: green if score >= this
COLOR_YELLOW_MIN = 6        # HTML report: yellow if score >= this (else red)

# --- Paths -------------------------------------------------------------------
DATASETS_DIR = "evals/datasets"
RUNS_DIR = "evals/runs"
