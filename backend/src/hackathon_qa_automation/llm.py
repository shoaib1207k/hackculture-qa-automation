"""The model every agent in the pipeline runs on -- Strands' own OpenAI provider."""

import logging
import os

from dotenv import load_dotenv
from strands.models import Model
from strands.models.openai import OpenAIModel
from strands.models.openai_responses import OpenAIResponsesModel

logger = logging.getLogger(__name__)

# Override with OPENAI_MODEL to compare models without touching code.
DEFAULT_MODEL_ID = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "none"


def build_model(reasoning_effort: str | None = None) -> Model:
    load_dotenv()
    # The boiler kept the key in OPEN_AI_API_KEY; the SDK default is OPENAI_API_KEY.
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_AI_API_KEY")
    if not key:
        raise RuntimeError("Set OPENAI_API_KEY (or OPEN_AI_API_KEY) in .env")
    model_id = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL_ID)
    if model_id.startswith("gpt-5.6"):
        # gpt-5.6 allows tool calls (which Strands structured output uses) only
        # on the Responses API, or on Chat Completions with reasoning off.
        # Effort is none | low | medium | high | xhigh | max.
        # Precedence: OPENAI_REASONING_EFFORT (global override, for experiments),
        # then the calling agent's own setting, then the default.
        effort = (os.environ.get("OPENAI_REASONING_EFFORT") or reasoning_effort
                  or DEFAULT_REASONING_EFFORT)
        if effort == "none":
            params = {"reasoning_effort": "none"}
        else:
            logger.debug("build_model model=%s provider=responses effort=%s", model_id, effort)
            return OpenAIResponsesModel(client_args={"api_key": key}, model_id=model_id,
                                        params={"reasoning": {"effort": effort}})
    elif model_id.startswith(("gpt-5", "o1", "o3", "o4")):
        params = {}  # other reasoning models reject `temperature`
    else:
        params = {"temperature": 0}
    logger.debug("build_model model=%s params=%s", model_id, params)
    return OpenAIModel(client_args={"api_key": key}, model_id=model_id, params=params)
