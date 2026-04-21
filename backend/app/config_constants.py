"""Centralized runtime constants — extracted from inline magic numbers (M-11).

These are NOT in ThresholdConfig (which is for scoring/coaching thresholds
that experts tune). These are infrastructure/runtime constants that change
only on architectural decisions.
"""

import os

AGENT_RECURSION_LIMIT: int = int(os.getenv("SPELIX_AGENT_RECURSION_LIMIT", "15"))
AGENT_TIMEOUT_SECONDS: float = float(os.getenv("SPELIX_AGENT_TIMEOUT", "60.0"))
DISTILLATION_TIMEOUT_SECONDS: float = float(os.getenv("SPELIX_DISTILLATION_TIMEOUT", "120.0"))
DISTILLATION_RECURSION_LIMIT: int = int(os.getenv("SPELIX_DISTILLATION_RECURSION_LIMIT", "15"))
JWKS_TTL_SECONDS: int = int(os.getenv("SPELIX_JWKS_TTL", "3600"))
MAX_ANALYSIS_RETRIES: int = int(os.getenv("SPELIX_MAX_ANALYSIS_RETRIES", "3"))

# LLM token limits — centralized for observability + future tuning.
LLM_MAX_TOKENS_CHAT: int = int(os.getenv("SPELIX_LLM_MAX_TOKENS_CHAT", "512"))
LLM_MAX_TOKENS_COACHING: int = int(os.getenv("SPELIX_LLM_MAX_TOKENS_COACHING", "2048"))
LLM_MAX_TOKENS_KEYFRAME: int = int(os.getenv("SPELIX_LLM_MAX_TOKENS_KEYFRAME", "2048"))
LLM_MAX_TOKENS_FAITHFULNESS: int = int(os.getenv("SPELIX_LLM_MAX_TOKENS_FAITHFULNESS", "1024"))
LLM_MAX_TOKENS_INGESTION: int = int(os.getenv("SPELIX_LLM_MAX_TOKENS_INGESTION", "500"))
