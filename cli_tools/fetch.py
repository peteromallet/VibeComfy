"""GitHub source fetching for ComfyUI nodes."""

import json
import re
import urllib.request
from typing import Dict, List, Tuple, Optional, Any


# Known repository mappings
KNOWN_REPOS = {
    'ComfyUI-WanVideoWrapper': 'kijai/ComfyUI-WanVideoWrapper',
    'comfyui_essentials': 'cubiq/ComfyUI_essentials',
    'ComfyUI_VLM_nodes': 'gokayfem/ComfyUI_VLM_nodes',
    'ComfyUI-VideoHelperSuite': 'Kosinkadink/ComfyUI-VideoHelperSuite',
    'rgthree-comfy': 'rgthree/rgthree-comfy',
    'ComfyUI-Easy-Use': 'yolain/ComfyUI-Easy-Use',
    'ComfyUI-Custom-Scripts': 'pythongosssss/ComfyUI-Custom-Scripts',
}

# Types that represent connections (not widgets)
CONNECTION_TYPES = {
    'MODEL', 'CLIP', 'VAE', 'LATENT', 'IMAGE', 'MASK', 'CONDITIONING',
    'CONTROL_NET', 'STYLE_MODEL', 'GLIGEN', 'UPSCALE_MODEL', 'SAMPLER',
    'SIGMAS', 'NOISE', 'GUIDER', 'WANVIDEOMODEL', 'WANVAE', 'WANVIDCONTEXT',
    'WANVIDEOTEXTEMBEDS', 'WANVIDIMAGE_EMBEDS', 'FETAARGS', 'CACHEARGS',
    'FLOWEDITARGS', 'SLGARGS', 'LOOPARGS', 'EXPERIMENTALARGS',
    'UNIANIMATE_POSE', 'FANTASYTALKING_EMBEDS', 'UNI3C_EMBEDS',
    'MULTITALK_EMBEDS', 'FREEINITARGS', 'VRAM_MANAGEMENTARGS',
    'VACEPATH', 'BLOCKSWAPARGS', 'FANTASYPORTRAITMODEL', 'FANTASYTALKINGMODEL'
}


def fetch_node_source(repo: str, commit: str, node_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch node source from GitHub and find the node class.

    Returns (source_code, url) or (None, None) if not found.
    """
    # Common file patterns for ComfyUI nodes
    file_patterns = ['nodes.py', '__init__.py', 'nodes/__init__.py', f'{node_name.lower()}.py']

    for pattern in file_patterns:
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{pattern}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.read().decode('utf-8'), url
        except:
            continue

    # Try to find any .py file containing the node
    api_url = f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"
    try:
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            tree = json.loads(resp.read().decode('utf-8'))
            py_files = [f['path'] for f in tree.get('tree', [])
                       if f['path'].endswith('.py') and 'test' not in f['path'].lower()]

            for py_file in py_files:
                url = f"https://raw.githubusercontent.com/{repo}/{commit}/{py_file}"
                try:
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        content = resp.read().decode('utf-8')
                        if f'class {node_name}' in content or f'"{node_name}"' in content:
                            return content, url
                except:
                    continue
    except:
        pass

    return None, None


def parse_input_types(source: str, node_name: str) -> Tuple[Optional[List], Optional[List]]:
    """Parse INPUT_TYPES from node source code.

    Returns (inputs, widgets) where each is a list of (name, type) tuples.
    """
    # Find the class
    class_pattern = rf'class\s+{node_name}\s*[:\(]'
    match = re.search(class_pattern, source)
    if not match:
        return None, None

    rest = source[match.start():]

    # Find INPUT_TYPES
    input_types_match = re.search(r'def\s+INPUT_TYPES\s*\([^)]*\)\s*:', rest)
    if not input_types_match:
        return None, None

    # Find return statement
    return_start = rest.find('return', input_types_match.end())
    if return_start == -1:
        return None, None

    brace_start = rest.find('{', return_start)
    if brace_start == -1:
        return None, None

    # Match braces
    depth = 0
    brace_end = brace_start
    for i, c in enumerate(rest[brace_start:]):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                brace_end = brace_start + i + 1
                break

    dict_str = rest[brace_start:brace_end]

    inputs = []
    widgets = []

    def parse_section(section_str):
        section_inputs = []
        section_widgets = []
        param_pattern = r'"(\w+)":\s*\(([^,\)]+)'
        for m in re.finditer(param_pattern, section_str):
            param_name = m.group(1)
            type_part = m.group(2).strip().strip('"\'').upper()
            if '_LIST' in type_part or type_part.islower():
                type_part = 'LIST'
            if type_part in CONNECTION_TYPES:
                section_inputs.append((param_name, type_part))
            else:
                section_widgets.append((param_name, type_part))
                if type_part == 'INT' and 'seed' in param_name.lower():
                    section_widgets.append((f'{param_name}_control', 'SEED_CONTROL'))
        return section_inputs, section_widgets

    for section_name in ['required', 'optional']:
        match = re.search(rf'"{section_name}"\s*:\s*\{{', dict_str)
        if match:
            start = match.end()
            depth = 1
            end = start
            for i, c in enumerate(dict_str[start:]):
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        end = start + i
                        break
            section_str = dict_str[start:end]
            inp, wid = parse_section(section_str)
            inputs.extend(inp)
            widgets.extend(wid)

    return inputs, widgets


def extract_class_code(source: str, class_name: str) -> Optional[str]:
    """Extract a class definition from source code."""
    class_pattern = rf'^class\s+{re.escape(class_name)}\s*[:\(]'
    match = re.search(class_pattern, source, re.MULTILINE)
    if not match:
        return None

    start = match.start()
    next_class = re.search(r'^class\s+\w+', source[match.end():], re.MULTILINE)
    if next_class:
        end = match.end() + next_class.start()
    else:
        end = len(source)

    return source[start:end].strip()


def search_source(source: str, term: str, context_lines: int = 3) -> List[Dict]:
    """Search source code for a term and return matches with context.

    Returns list of {'line_num': int, 'line': str, 'context_before': [str], 'context_after': [str]}
    """
    lines = source.split('\n')
    matches = []

    for i, line in enumerate(lines):
        if term.lower() in line.lower():
            match = {
                'line_num': i + 1,
                'line': line,
                'context_before': lines[max(0, i - context_lines):i],
                'context_after': lines[i + 1:min(len(lines), i + 1 + context_lines)],
            }
            matches.append(match)

    return matches


def get_node_repo_info(node: Dict) -> Dict:
    """Extract repository info from node properties.

    Returns {'repo': str, 'commit': str, 'node_name': str} or partial dict if missing.
    """
    props = node.get('properties', {})
    repo = props.get('aux_id')
    commit = props.get('ver')
    cnr_id = props.get('cnr_id')
    node_name = props.get('Node name for S&R') or node.get('type', '')

    # Try to infer repo from cnr_id
    if not repo and cnr_id:
        for key, value in KNOWN_REPOS.items():
            if key.lower() in cnr_id.lower():
                repo = value
                break

    return {
        'repo': repo,
        'commit': commit,
        'node_name': node_name,
        'cnr_id': cnr_id,
    }
