"""
Output format utilities for refinement agents.
Defines and processes SEARCH/REPLACE formats that are easy for LLMs to generate.
"""

import re
from typing import List, Tuple

class SearchReplaceOperation:
    """Represents a single SEARCH/REPLACE operation."""
    def __init__(self, search_text: str, replace_text: str):
        self.search_text = search_text
        self.replace_text = replace_text

class SearchReplaceFormatter:
    """Handles SEARCH/REPLACE format for LLM output."""
    
    @staticmethod
    def get_format_instructions() -> str:
        """Returns instructions for LLMs on how to use the SEARCH/REPLACE format."""
        return """
Response format: Use the following SEARCH/REPLACE format to specify your changes.

Every *SEARCH/REPLACE* edit must use this format:
1. The start of search block: <<<<<<< SEARCH
2. A contiguous chunk of lines to search for in the existing source code
3. The dividing line: =======
4. The lines to replace into the source code
5. The end of the replace block: >>>>>>> REPLACE

Examples:

```rust
<<<<<<< SEARCH
    assert(y > x);
=======
    assert(y > x) by {
        assert(x > 0);
    }
>>>>>>> REPLACE
```

```rust
<<<<<<< SEARCH
    proof fn rev_map_union(s1: Set<int>, s2: Set<int>, x: int, f: spec_fn(int) -> int)
        requires
            s1.map(f).union(s2.map(f)).contains(x)
        ensures
            exists |y:int| s1.union(s2).contains(y) && f(y) == x 
    {
    }
=======
    proof fn rev_map_union(s1: Set<int>, s2: Set<int>, x: int, f: spec_fn(int) -> int)
        requires
            s1.map(f).union(s2.map(f)).contains(x)
        ensures
            exists |y:int| s1.union(s2).contains(y) && f(y) == x 
    {
        if (s1.map(f).contains(x)) {
        } else {
        }
    }
>>>>>>> REPLACE
```

```rust
<<<<<<< SEARCH
    let v = Vec::new();
=======
    let v = Vec::new();
    proof {
        assert(v@.len() == 0);
    }
>>>>>>> REPLACE
```

Rules:
1. The *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION
2. If you want to add '        print(x)', write it with all spaces
3. Use exact text matching - be precise with whitespace and indentation
4. Include enough context in SEARCH to uniquely identify the location
5. Multiple SEARCH/REPLACE blocks are allowed
6. To delete code, use empty REPLACE section
7. To insert code, include the surrounding context in SEARCH
8. Use ```rust``` to wrap the code. DO NOT use any -/+ symbols in the beginning of the lines.

Only specify the changes needed to fix the error. The search text should be exact and unique.
"""

    @staticmethod
    def parse_search_replace_response(response: str) -> List[SearchReplaceOperation]:
        """Parse LLM response in SEARCH/REPLACE format into SearchReplaceOperation objects."""
        operations = []
        
        # Remove outer code block markers if present
        response = re.sub(r'```(?:rust|verus|python)?\s*\n?|```\s*$', '', response, flags=re.MULTILINE)
        
        # Pattern for SEARCH/REPLACE blocks
        pattern = r'<{7}\s*SEARCH\s*\n(.*?)\n={7}\s*\n(.*?)\n>{7}\s*REPLACE'
        
        for match in re.finditer(pattern, response, re.DOTALL):
            search_text = match.group(1)
            replace_text = match.group(2)
            operations.append(SearchReplaceOperation(search_text, replace_text))
        
        return operations

    @staticmethod
    def apply_search_replace_operations(original_code: str, operations: List[SearchReplaceOperation]) -> str:
        """Apply SEARCH/REPLACE operations to the original code and return the modified code."""
        modified_code = original_code
        
        for op in operations:
            modified_code = SearchReplaceFormatter._apply_single_operation(modified_code, op)
        
        return modified_code
    
    @staticmethod
    def _apply_single_operation(code: str, op: SearchReplaceOperation) -> str:
        """Apply a single SEARCH/REPLACE operation with priority-based matching."""
        # Check for direct string match first
        if op.search_text in code:
            # For multiple matches, prioritize ERROR_SUFFIX lines
            matches = SearchReplaceFormatter._find_all_matches(code, op.search_text)
            if len(matches) > 1:
                # Find the best match to replace (prioritize ERROR_SUFFIX lines)
                best_match = SearchReplaceFormatter._select_best_match(code, matches)
                return SearchReplaceFormatter._replace_at_position(code, op, best_match)
            else:
                # Single match - direct replacement
                return code.replace(op.search_text, op.replace_text, 1)
        else:
            # Try with normalized whitespace for more flexibility
            return SearchReplaceFormatter._apply_with_normalized_whitespace(code, op)
    
    @staticmethod
    def _find_all_matches(code: str, search_text: str) -> List[int]:
        """Find all starting positions of search_text in code."""
        matches = []
        start = 0
        while True:
            pos = code.find(search_text, start)
            if pos == -1:
                break
            matches.append(pos)
            start = pos + 1
        return matches
    
    @staticmethod
    def _select_best_match(code: str, matches: List[int]) -> int:
        """Select the best match position (returns first match)."""
        return matches[0] if matches else 0
    
    @staticmethod
    def _replace_at_position(code: str, op: SearchReplaceOperation, position: int) -> str:
        """Replace search_text with replace_text at the specified position."""
        before = code[:position]
        after = code[position + len(op.search_text):]
        return before + op.replace_text + after
    
    @staticmethod
    def _apply_with_normalized_whitespace(code: str, op: SearchReplaceOperation) -> str:
        """Apply operation with normalized whitespace matching."""
        search_lines = op.search_text.splitlines()
        code_lines = code.splitlines()
        
        # Find all potential matches with normalized whitespace
        matches = []
        for i in range(len(code_lines) - len(search_lines) + 1):
            match = True
            for j, search_line in enumerate(search_lines):
                if search_line.strip() != code_lines[i + j].strip():
                    match = False
                    break
            if match:
                matches.append(i)
        
        if not matches:
            return code
        
        # Select the best match (prioritize ERROR_SUFFIX lines)
        best_match_idx = SearchReplaceFormatter._select_best_line_match(code_lines, matches, search_lines)
        
        # Apply the replacement at the best match
        return SearchReplaceFormatter._replace_at_line_index(code_lines, op, best_match_idx)
    
    @staticmethod
    def _select_best_line_match(code_lines: List[str], matches: List[int], search_lines: List[str]) -> int:
        """Select the best line match (returns first match)."""
        return matches[0] if matches else 0
    
    @staticmethod
    def _replace_at_line_index(code_lines: List[str], op: SearchReplaceOperation, line_index: int) -> str:
        """Replace lines starting at line_index with the replacement text."""
        search_lines = op.search_text.splitlines()
        
        # Preserve the indentation of the first line
        base_indent = len(code_lines[line_index]) - len(code_lines[line_index].lstrip())
        
        # Prepare replacement lines with proper indentation
        replace_lines = op.replace_text.splitlines()
        if replace_lines:
            # For the first line, use the existing indentation
            if replace_lines[0].strip():
                replace_lines[0] = ' ' * base_indent + replace_lines[0].lstrip()
            
            # For subsequent lines, preserve their relative indentation
            for k in range(1, len(replace_lines)):
                if replace_lines[k].strip():  # Don't modify empty lines
                    # Calculate relative indentation from original
                    original_indent = len(replace_lines[k]) - len(replace_lines[k].lstrip())
                    replace_lines[k] = ' ' * (base_indent + original_indent) + replace_lines[k].lstrip()
        
        # Replace the lines
        code_lines[line_index:line_index + len(search_lines)] = replace_lines
        return '\n'.join(code_lines)


    @staticmethod
    def validate_operations(original_code: str, operations: List[SearchReplaceOperation]) -> Tuple[bool, str]:
        """Validate that SEARCH/REPLACE operations can be safely applied."""
        for i, op in enumerate(operations):
            if op.search_text not in original_code:
                # Try with normalized whitespace
                search_lines = op.search_text.splitlines()
                code_lines = original_code.splitlines()
                
                found = False
                for j in range(len(code_lines) - len(search_lines) + 1):
                    match = True
                    for k, search_line in enumerate(search_lines):
                        if search_line.strip() != code_lines[j + k].strip():
                            match = False
                            break
                    if match:
                        found = True
                        break
                
                if not found:
                    return False, f"SEARCH block {i+1} not found: '{op.search_text[:50]}...'"
        
        return True, "Valid"

def apply_search_replace_format(original_code: str, llm_response: str) -> Tuple[str, bool, str]:
    """
    Apply SEARCH/REPLACE format response to original code.

    Returns:
        tuple: (modified_code, success, error_message)
    """
    return _apply_search_replace_format(original_code, llm_response)

def _apply_search_replace_format(original_code: str, llm_response: str) -> Tuple[str, bool, str]:
    try:
        operations = SearchReplaceFormatter.parse_search_replace_response(llm_response)
        
        if not operations:
            # If no SEARCH/REPLACE operations found, try to extract code blocks as fallback
            code_blocks = re.findall(r'```(?:rust|verus)?\s*\n(.*?)```', llm_response, re.DOTALL)
            if code_blocks:
                return code_blocks[0].strip(), True, "Fallback to code block extraction"
            return original_code, False, "No SEARCH/REPLACE operations or code blocks found"
        
        # Validate operations
        valid, message = SearchReplaceFormatter.validate_operations(original_code, operations)
        if not valid:
            return original_code, False, f"Invalid SEARCH/REPLACE operations: {message}"
        
        # Apply operations
        modified_code = SearchReplaceFormatter.apply_search_replace_operations(original_code, operations)
        return modified_code, True, f"Applied {len(operations)} SEARCH/REPLACE operations"
        
    except Exception as e:
        return original_code, False, f"Error processing SEARCH/REPLACE format: {str(e)}"
