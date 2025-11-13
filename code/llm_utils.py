# Copyright (c) Microsoft Corporation. #
# Licensed under the MIT license.      #

"""
LLM Utility Functions
Standalone utilities for calling LLM with various formats.
Provides search-replace format for precise code modifications.
"""

import time
from typing import List
from pathlib import Path

from output_format import SearchReplaceFormatter, apply_search_replace_format


def call_llm_with_search_replace_format(
    llm,
    logger,
    llm_prompt_dir: Path,
    engine: str,
    instruction: str,
    query: str,
    system: str,
    original_code: str = "",
    examples: List = None,
    answer_num: int = 1,
    max_tokens: int = 4096,
    temp: float = 1.0,
) -> List[str]:
    """
    Call LLM with SEARCH/REPLACE format instructions and handle the response.

    This function wraps the LLM call to:
    1. Add SEARCH/REPLACE format instructions to the system prompt
    2. Call the LLM
    3. Parse and apply the SEARCH/REPLACE operations
    4. Return only successfully modified code

    Args:
        llm: LLM instance to use for inference
        logger: Logger instance
        llm_prompt_dir: Directory to save prompts for debugging
        engine: LLM engine/model name
        instruction: Base instruction for the LLM
        query: The specific query/task
        system: System prompt
        original_code: Original code to apply changes to
        examples: Optional list of examples for few-shot learning (default: [])
        answer_num: Number of responses to generate
        max_tokens: Maximum tokens for response
        temp: Temperature for sampling

    Returns:
        List of modified code strings (successfully applied patches only)
    """
    if examples is None:
        examples = []

    # Add SEARCH/REPLACE format instructions to the system prompt
    search_replace_instructions = SearchReplaceFormatter.get_format_instructions()
    system = system + "\n\n" + search_replace_instructions

    # Log the prompt for debugging
    time_stamp = str(time.time())
    (llm_prompt_dir / f"{time_stamp}-input.txt").write_text(
        instruction + "\n\n" + query, encoding="utf-8"
    )

    # Call LLM with examples
    responses = llm.infer_llm(
        engine,
        instruction,
        examples,
        query,
        system,
        answer_num=answer_num,
        max_tokens=max_tokens,
        temp=temp
    )

    # Process responses using SEARCH/REPLACE format
    modified_codes = []
    for i, response in enumerate(responses):
        (llm_prompt_dir / f"{time_stamp}-output-{i}.txt").write_text(
            response, encoding="utf-8"
        )

        modified_code, success, message = apply_search_replace_format(original_code, response)
        if success:
            logger.info(f"Successfully applied SEARCH/REPLACE format: {message}")
            modified_codes.append(modified_code)
        else:
            # Discard the response if it fails to apply the SEARCH/REPLACE format
            logger.warning(f"Failed to apply SEARCH/REPLACE format: {message}")

    return modified_codes


def call_llm_with_full_return(
    llm,
    logger,
    llm_prompt_dir: Path,
    engine: str,
    instruction: str,
    query: str,
    system: str,
    answer_num: int = 1,
    max_tokens: int = 4096,
    temp: float = 1.0,
) -> List[str]:
    """
    Call LLM expecting full code return (not search-replace format).

    This is used for initial code generation where there's no original code to modify.

    Args:
        llm: LLM instance to use for inference
        logger: Logger instance
        llm_prompt_dir: Directory to save prompts for debugging
        engine: LLM engine/model name
        instruction: Base instruction for the LLM
        query: The specific query/task
        system: System prompt
        answer_num: Number of responses to generate
        max_tokens: Maximum tokens for response
        temp: Temperature for sampling

    Returns:
        List of LLM responses
    """
    # Add standard instructions
    query += "\n\nDo not add `proof { ... }` to in the body of the `proof fn` function and `spec fn` function."
    query += "\n\nPlease return the full code with the changes applied. The code should be surrounded by ```verus and ```."

    # Log the prompt for debugging
    time_stamp = str(time.time())
    (llm_prompt_dir / f"{time_stamp}-input.txt").write_text(
        instruction + "\n\n" + query, encoding="utf-8"
    )

    # Call LLM (no examples)
    responses = llm.infer_llm(
        engine,
        instruction,
        [],  # No examples
        query,
        system,
        answer_num=answer_num,
        max_tokens=max_tokens,
        temp=temp
    )

    # Log responses
    for i, response in enumerate(responses):
        (llm_prompt_dir / f"{time_stamp}-output-{i}.txt").write_text(
            response, encoding="utf-8"
        )

    return responses
