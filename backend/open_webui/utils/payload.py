import json
from typing import Callable, Optional

from open_webui.utils.misc import (
    add_or_update_system_message,
    deep_update,
    replace_system_message_content,
)
from open_webui.utils.task import prompt_template, prompt_variables_template


async def resolve_system_prompt(
    system: Optional[str],
    metadata: Optional[dict] = None,
    user=None,
) -> str:
    if not system:
        return ''

    if metadata:
        variables = metadata.get('variables', {})
        if variables:
            system = prompt_variables_template(system, variables)

    return await prompt_template(system, user)


async def apply_system_prompt_to_body(
    system: Optional[str],
    form_data: dict,
    metadata: Optional[dict] = None,
    user=None,
    replace: bool = False,
) -> dict:
    system = await resolve_system_prompt(system, metadata, user)
    if not system:
        return form_data

    if replace:
        form_data['messages'] = replace_system_message_content(system, form_data.get('messages', []))
    else:
        form_data['messages'] = add_or_update_system_message(system, form_data.get('messages', []))
    return form_data


def apply_model_params_to_body(params: dict, form_data: dict, mappings: dict[str, Callable]) -> dict:
    if not params:
        return form_data

    for key, value in params.items():
        if value is not None:
            if key in mappings:
                cast_func = mappings[key]
                if isinstance(cast_func, Callable):
                    form_data[key] = cast_func(value)
            else:
                form_data[key] = value
    return form_data


def remove_open_webui_params(params: dict) -> dict:
    """Remove parameters consumed internally by Open WebUI."""
    open_webui_params = {
        'stream_response': bool,
        'stream_delta_chunk_size': int,
        'function_calling': str,
        'reasoning_tags': list,
        'compact_token_threshold': int,
        'system': str,
    }

    for key in list(params.keys()):
        if key in open_webui_params:
            del params[key]
    return params


def apply_model_params_to_body_openai(params: dict, form_data: dict) -> dict:
    params = remove_open_webui_params(params)

    custom_params = params.pop('custom_params', {})
    if custom_params:
        for key, value in custom_params.items():
            if isinstance(value, str):
                try:
                    custom_params[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass
        params = deep_update(params, custom_params)

    mappings = {
        'temperature': float,
        'top_p': float,
        'min_p': float,
        'max_tokens': int,
        'frequency_penalty': float,
        'presence_penalty': float,
        'reasoning_effort': str,
        'seed': lambda x: x,
        'stop': lambda x: [bytes(s, 'utf-8').decode('unicode_escape') for s in x],
        'logit_bias': lambda x: x,
        'response_format': dict,
    }
    return apply_model_params_to_body(params, form_data, mappings)
