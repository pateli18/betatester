import json
import logging
from typing import AsyncGenerator

import httpx

from .betatester_types import OpenAiChatInput

logger = logging.getLogger("betatester")

TIMEOUT = 30


async def send_openai_request(
    client: httpx.AsyncClient,
    request_payload: dict,
    route: str,
    api_key: str,
) -> dict:
    url = f"https://api.openai.com/v1/{route}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = await client.post(
        url,
        headers=headers,
        json=request_payload,
        timeout=httpx.Timeout(TIMEOUT),
    )
    if response.status_code != 200:
        response_body = await response.aread()
        logger.error(
            f"Error in OpenAI chat API: {response.status_code} {response_body.decode()}"
        )
    response.raise_for_status()
    response_output = response.json()
    return response_output


async def _stream_openai_chat_api(
    client: httpx.AsyncClient,
    openai_input: OpenAiChatInput,
    api_key: str,
) -> AsyncGenerator[str, None]:
    async with client.stream(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        timeout=httpx.Timeout(TIMEOUT),
        headers={
            "Authorization": f"Bearer {api_key}",
        },
        json=openai_input.data,
    ) as response:
        if response.status_code != 200:
            # read the response to log the error
            response_body = await response.aread()
            logger.error(
                f"Error in OpenAI chat API: {response.status_code} {response_body.decode()}"
            )
        response.raise_for_status()
        async for chunk in response.aiter_text():
            yield chunk


async def openai_stream_response_generator(
    client: httpx.AsyncClient,
    openai_chat_input: OpenAiChatInput,
    api_key: str,
) -> AsyncGenerator[dict, None]:
    content = ""
    func_call = {"arguments": ""}
    error_message = None
    try:
        async for response in _stream_openai_chat_api(
            client, openai_chat_input, api_key
        ):
            for block_raw in response.split("\n\n"):
                for line in block_raw.split("\n"):
                    if line.startswith("data:"):
                        json_str = line.replace("data:", "").strip()
                        if json_str == "[DONE]":
                            break
                        else:
                            try:
                                block = json.loads(json_str)
                            # skip any json decode errors
                            except Exception as e:
                                logger.debug(e)
                                continue

                            # we assume that we only need to look at the first choice
                            choice = block["choices"][0]
                            delta = choice.get("delta")
                            if delta is None:
                                continue
                            elif "function_call" in delta:
                                name = delta["function_call"].get("name")
                                if name:
                                    func_call["name"] = name
                                arguments = delta["function_call"].get(
                                    "arguments"
                                )
                                if arguments:
                                    func_call["arguments"] += arguments
                            elif "content" in delta:
                                content += delta["content"]
                                yield {"content": content}
        if func_call.get("name"):
            yield {"func_call": func_call}

    except Exception as e:
        logger.error("Error in openai_stream_response_generator %s", str(e))
        yield {"error": error_message}
