# =========================================================================================
# API Call Module (English Version)
# =========================================================================================
# This script provides functions for calling various language model APIs,
# including a mechanism to handle retries, streaming, JSON-formatted responses,
# and environment-based configuration. It also offers helper functions for
# handling text similarity checks.
# =========================================================================================

import json
import os
import time
import logging
import yaml

from difflib import SequenceMatcher
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------------------
# String similarity utility functions
# -----------------------------------------------------------------------------------------

def is_similar(a, b, threshold=0.8):
    """
    Checks whether two strings 'a' and 'b' have a similarity ratio that is
    at least 'threshold'. The ratio is computed via difflib.SequenceMatcher.
    """
    return SequenceMatcher(None, a, b).ratio() >= threshold

def remove_similar_prefix(text, prefix, threshold=0.8):
    """
    Removes a prefix from 'text' if the beginning of 'text' is sufficiently
    similar to 'prefix', according to the specified 'threshold'.
    """
    if is_similar(text[:len(prefix)], prefix, threshold):
        return text[len(prefix):].strip()
    return text

# -----------------------------------------------------------------------------------------
# Environment loading
# -----------------------------------------------------------------------------------------

def load_env():
    """
    Loads YAML configuration from 'config/env.yaml' and retrieves a 'services' object
    that contains various API endpoints and credentials.
    """
    with open("config/env.yaml", "r") as f:
        service = yaml.safe_load(f)['services']
    return service

global services
services = load_env()

# -----------------------------------------------------------------------------------------
# API call functions
# -----------------------------------------------------------------------------------------

def api_call(messages, model="deepseek", temperature=1.0, max_tokens=4096,
             max_retries=10, json_format=False, stream=False):
    """
    Performs a chat completion request using the specified 'model'. The function
    supports different endpoints such as 'gpt', 'qwen', 'deepseek', or 'claude'
    based on the 'model' string. It also applies a retry mechanism up to 'max_retries'
    times. If 'json_format' is True, the function attempts to parse JSON in the
    response. If 'stream' is True, partial output tokens may be streamed.

    :param messages: A list of dict objects containing 'role' and 'content'.
    :param model: The model name or identifier (e.g., "deepseek-chat").
    :param temperature: The temperature parameter for sampling randomness.
    :param max_tokens: Maximum number of tokens allowed in the response.
    :param max_retries: Number of retry attempts upon failure.
    :param json_format: If True, expects the model to return JSON.
    :param stream: If True, uses streaming output from the server.
    :return: The content of the first choice in the response, either as a string or
             a parsed JSON object if 'json_format' is True.
    """
    if "gpt" in model or "o1" in model:
        api_key = services['openai']['api_key']
        base_url = services['openai']['base_url']
    elif "qwen" in model:
        api_key = services['qwen']['api_key']
        base_url = services['qwen']['base_url']
    elif "deepseek" in model:
        api_key = services['deepseek']['api_key']
        base_url = f"{services['deepseek']['base_url']}"
    elif "claude" in model:
        api_key = services['claude']['api_key']
        base_url = services['claude']['base_url']
    else:
        raise ValueError(f"Unknown model identifier: {model}")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    for attempt in range(max_retries):
        try:
            if not json_format:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=stream
                )
                if not response.choices[0].message.content:
                    continue
                return response.choices[0].message.content
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    stream=stream
                )
                if not response.choices[0].message.content:
                    continue
                json_response = eval(response.choices[0].message.content)
                return json_response

        except Exception as e:
            logger.error(f"Error while calling API: {str(e)}")
            time.sleep(2 ** (attempt + 1))
            continue

    raise Exception("Max retries reached. API call failed.")

def api_call_completion(messages, model="deepseek-chat", stop_list=None):
    """
    Similar to 'api_call' but specifically for a scenario requiring a 'stop' argument
    to limit the response. Includes a simple retry mechanism.

    :param messages: A list of message dicts with 'role' and 'content'.
    :param model: The model name or identifier.
    :param stop_list: A list of stop strings to control the generation halting.
    :return: The first chunk of response text from the model.
    """
    if "gpt" in model or "o1" in model:
        api_key = services['openai']['api_key']
        base_url = services['openai']['base_url']
    elif "qwen" in model:
        api_key = services['qwen']['api_key']
        base_url = services['qwen']['base_url']
    elif "deepseek" in model:
        api_key = services['deepseek']['api_key']
        base_url = f"{services['deepseek']['base_url']}"
    elif "claude" in model:
        api_key = services['claude']['api_key']
        base_url = services['claude']['base_url']
    else:
        raise ValueError(f"Unknown model identifier: {model}")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key
    )

    for attempt in range(10):
        try:
            if stop_list is not None and len(stop_list) > 0:
                prefix = stop_list[0]
                prefix = f"Step {int(prefix[5]) - 1}:"
            else:
                prefix = ""

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                stop=stop_list,
                stream=False,
                max_tokens=4096,
                temperature=0.0,
            )
            current_text = response.choices[0].message.content
            if current_text:
                return current_text
            else:
                logger.info("Empty response returned. Retrying...")
                continue

        except Exception as e:
            logger.error(f"Error on attempt {attempt+1}: {str(e)}")
            time.sleep(2 ** (attempt + 1))

    raise RuntimeError("Max retries reached without successful completion.")

# -----------------------------------------------------------------------------------------
# Example usage demonstration
# -----------------------------------------------------------------------------------------

if __name__ == "__main__":
    """
    This is an example usage that sends a request to the 'deepseek-chat' model.
    """
    messages = [
        {
            "role": "user",
            "content": "https://en.wikipedia.org/wiki/IEEE_Frank_Rosenblatt_Award"
        }
    ]
    # The model name can be replaced based on your environment or specific usage
    print(api_call(messages, model="deepseek-chat"))
