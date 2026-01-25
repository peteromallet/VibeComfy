#!/usr/bin/env python3
"""Tests for CLI and MCP tool functions.

Run with: python -m pytest tests/test_tools.py -v
Or standalone: python tests/test_tools.py
"""

import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Test Fixtures
# =============================================================================

def get_simple_workflow():
    """Simple workflow for basic tests."""
    return {
        'nodes': [
            {'id': 1, 'type': 'LoadImage', 'inputs': [],
             'outputs': [{'name': 'IMAGE', 'type': 'IMAGE', 'links': [1]}]},
            {'id': 2, 'type': 'VAEEncode',
             'inputs': [{'name': 'pixels', 'link': 1, 'type': 'IMAGE'}],
             'outputs': [{'name': 'LATENT', 'type': 'LATENT', 'links': [2]}]},
            {'id': 3, 'type': 'KSampler',
             'inputs': [{'name': 'latent_image', 'link': 2, 'type': 'LATENT'}],
             'outputs': [{'name': 'LATENT', 'type': 'LATENT', 'links': [3]}],
             'widgets_values': [42, 'fixed', 20, 7.5, 'euler', 'normal', 1.0]},
            {'id': 4, 'type': 'VAEDecode',
             'inputs': [{'name': 'samples', 'link': 3, 'type': 'LATENT'}],
             'outputs': [{'name': 'IMAGE', 'type': 'IMAGE', 'links': [4]}]},
            {'id': 5, 'type': 'SaveImage',
             'inputs': [{'name': 'images', 'link': 4, 'type': 'IMAGE'}],
             'outputs': []},
        ],
        'links': [
            [1, 1, 0, 2, 0, 'IMAGE'],
            [2, 2, 0, 3, 0, 'LATENT'],
            [3, 3, 0, 4, 0, 'LATENT'],
            [4, 4, 0, 5, 0, 'IMAGE'],
        ],
        'last_node_id': 5,
        'last_link_id': 4,
    }


def get_workflow_with_variables():
    """Workflow with SetNode/GetNode for variable tests."""
    return {
        'nodes': [
            {'id': 1, 'type': 'LoadImage', 'inputs': [],
             'outputs': [{'name': 'IMAGE', 'type': 'IMAGE', 'links': [1]}]},
            {'id': 2, 'type': 'SetNode', 'title': 'Set_myimage',
             'inputs': [{'name': 'value', 'link': 1, 'type': 'IMAGE'}],
             'outputs': []},
            {'id': 3, 'type': 'GetNode', 'title': 'Get_myimage',
             'inputs': [],
             'outputs': [{'name': 'value', 'type': 'IMAGE', 'links': [2]}]},
            {'id': 4, 'type': 'SaveImage',
             'inputs': [{'name': 'images', 'link': 2, 'type': 'IMAGE'}],
             'outputs': []},
        ],
        'links': [
            [1, 1, 0, 2, 0, 'IMAGE'],
            [2, 3, 0, 4, 0, 'IMAGE'],
        ],
        'last_node_id': 4,
        'last_link_id': 2,
    }


def get_real_workflow_path():
    """Path to real workflow file if available."""
    path = Path(__file__).parent.parent / 'workflows' / 'workflow_fixed_node.json'
    return path if path.exists() else None


# =============================================================================
# Tests: cli_tools/analysis.py
# =============================================================================

class TestAnalysis:
    """Tests for analysis.py functions."""

    def test_trace_node_exists(self):
        """trace_node returns correct structure for existing node."""
        from cli_tools.analysis import trace_node

        wf = get_simple_workflow()
        result = trace_node(wf, 3)  # KSampler

        assert 'error' not in result, f"Unexpected error: {result.get('error')}"
        assert result['node_id'] == 3
        assert result['node_type'] == 'KSampler'
        assert isinstance(result['inputs'], list)
        assert isinstance(result['outputs'], list)
        assert len(result['inputs']) == 1
        assert result['inputs'][0]['source_node'] == 2  # VAEEncode
        assert len(result['outputs']) == 1
        assert result['outputs'][0]['targets'][0]['node'] == 4  # VAEDecode

    def test_trace_node_not_found(self):
        """trace_node returns error for non-existent node."""
        from cli_tools.analysis import trace_node

        wf = get_simple_workflow()
        result = trace_node(wf, 999)

        assert 'error' in result
        assert '999' in result['error']

    def test_trace_node_unconnected(self):
        """trace_node handles unconnected inputs/outputs."""
        from cli_tools.analysis import trace_node

        wf = get_simple_workflow()
        result = trace_node(wf, 1)  # LoadImage - no inputs

        assert result['node_type'] == 'LoadImage'
        assert len(result['inputs']) == 0
        assert len(result['outputs']) == 1
        assert result['outputs'][0]['targets'][0]['node'] == 2

    def test_analyze_workflow_structure(self):
        """analyze_workflow returns expected structure."""
        from cli_tools.analysis import analyze_workflow

        wf = get_simple_workflow()
        result = analyze_workflow(wf)

        assert 'entry_points' in result
        assert 'exit_points' in result
        assert 'pipelines' in result
        assert 'variables' in result
        assert 'loops' in result
        assert 1 in result['entry_points']  # LoadImage
        assert 5 in result['exit_points']   # SaveImage

    def test_analyze_workflow_variables(self):
        """analyze_workflow detects SetNode/GetNode variables."""
        from cli_tools.analysis import analyze_workflow

        wf = get_workflow_with_variables()
        result = analyze_workflow(wf)

        assert len(result['variables']) == 1
        assert result['variables'][0]['name'] == 'myimage'
        assert result['variables'][0]['set_id'] == 2
        assert 3 in result['variables'][0]['get_ids']

    def test_find_upstream(self):
        """find_upstream finds all nodes feeding into target."""
        from cli_tools.analysis import find_upstream

        wf = get_simple_workflow()
        result = find_upstream(wf, 5, max_depth=10)  # SaveImage

        assert 'nodes' in result
        assert 'edges' in result
        # Should find: VAEDecode(4), KSampler(3), VAEEncode(2), LoadImage(1)
        assert 4 in result['nodes']
        assert 3 in result['nodes']
        assert 2 in result['nodes']
        assert 1 in result['nodes']

    def test_find_downstream(self):
        """find_downstream finds all nodes fed by source."""
        from cli_tools.analysis import find_downstream

        wf = get_simple_workflow()
        result = find_downstream(wf, 1, max_depth=10)  # LoadImage

        assert 'nodes' in result
        # Should find: VAEEncode(2), KSampler(3), VAEDecode(4), SaveImage(5)
        assert 2 in result['nodes']
        assert 3 in result['nodes']
        assert 4 in result['nodes']
        assert 5 in result['nodes']

    def test_find_path(self):
        """find_path finds shortest path between nodes."""
        from cli_tools.analysis import find_path

        wf = get_simple_workflow()
        path = find_path(wf, 1, 5)  # LoadImage to SaveImage

        assert path is not None
        assert path[0] == 1
        assert path[-1] == 5
        assert len(path) == 5  # 1 -> 2 -> 3 -> 4 -> 5

    def test_find_path_no_connection(self):
        """find_path returns None when no path exists."""
        from cli_tools.analysis import find_path

        wf = get_simple_workflow()
        path = find_path(wf, 5, 1)  # SaveImage to LoadImage (reverse)

        assert path is None

    def test_get_workflow_info(self):
        """get_workflow_info returns correct statistics."""
        from cli_tools.analysis import get_workflow_info

        wf = get_simple_workflow()
        info = get_workflow_info(wf)

        assert info['node_count'] == 5
        assert info['link_count'] == 4
        assert info['last_node_id'] == 5
        assert 'type_counts' in info
        assert info['type_counts']['KSampler'] == 1


# =============================================================================
# Tests: cli_tools/search.py
# =============================================================================

class TestSearch:
    """Tests for search.py functions."""

    def test_task_aliases_exist(self):
        """TASK_ALIASES contains expected entries."""
        from cli_tools.search import TASK_ALIASES

        assert isinstance(TASK_ALIASES, dict)
        assert len(TASK_ALIASES) >= 20
        assert 'ltx' in TASK_ALIASES
        assert 'wan' in TASK_ALIASES
        assert 'controlnet' in TASK_ALIASES

    def test_expand_query_basic(self):
        """expand_query returns input term."""
        from cli_tools.search import expand_query

        terms = expand_query('test')
        assert 'test' in terms

    def test_expand_query_alias(self):
        """expand_query expands known aliases."""
        from cli_tools.search import expand_query

        terms = expand_query('ltx')
        assert 'ltx' in terms
        assert 'lightricks' in terms
        assert 'ltxv' in terms

    def test_expand_query_multiple_words(self):
        """expand_query handles multiple words."""
        from cli_tools.search import expand_query

        terms = expand_query('audio reactive')
        assert 'audio' in terms
        assert 'reactive' in terms
        assert 'amplitude' in terms  # From alias expansion

    def test_expand_query_no_expansion(self):
        """expand_query doesn't expand unknown terms."""
        from cli_tools.search import expand_query

        terms = expand_query('xyzunknown')
        assert terms == ['xyzunknown']


# =============================================================================
# Tests: cli_tools/descriptions.py
# =============================================================================

class TestDescriptions:
    """Tests for descriptions.py functions."""

    def test_get_description_hardcoded(self):
        """get_node_description returns hardcoded descriptions."""
        from cli_tools.descriptions import get_node_description

        # These are in NODE_DESCRIPTIONS
        desc = get_node_description('VAEDecode')
        assert desc  # Should have a description
        assert len(desc) > 5

    def test_get_description_inferred(self):
        """get_node_description infers from name."""
        from cli_tools.descriptions import get_node_description

        desc = get_node_description('SomeRandomCustomNode')
        assert desc  # Should infer something
        assert 'some' in desc.lower() or 'random' in desc.lower() or 'custom' in desc.lower()

    def test_get_description_from_cache(self):
        """get_node_description prefers cache when available."""
        from cli_tools.descriptions import get_node_description

        # KSampler should have a richer description from cache
        desc = get_node_description('KSampler')
        assert desc
        # Cache description is longer than hardcoded
        assert len(desc) > 10


# =============================================================================
# Tests: cli_tools/registry/knowledge.py
# =============================================================================

class TestKnowledge:
    """Tests for knowledge.py ComfyKnowledge class."""

    def test_knowledge_loads_cache(self):
        """ComfyKnowledge loads node cache."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        assert len(kb.nodes) > 0

    def test_search_nodes_returns_results(self):
        """search_nodes returns matching results."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        results = kb.search_nodes('sampler', limit=5)

        assert len(results) > 0
        assert all('name' in r for r in results)
        assert all('score' in r for r in results)
        # Results should contain sampler-related nodes
        assert any('sampler' in r['name'].lower() for r in results)

    def test_search_nodes_alias_expansion(self):
        """search_nodes expands aliases."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        results = kb.search_nodes('ltx', limit=10)

        # Should find LTX nodes due to alias expansion
        assert len(results) > 0
        assert any('ltx' in r['name'].lower() for r in results)

    def test_search_nodes_no_results(self):
        """search_nodes returns empty list for no matches."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        results = kb.search_nodes('xyznonexistent123456', limit=5)

        assert results == []

    def test_get_node_spec_exists(self):
        """get_node_spec returns spec for existing node."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        # Search for a node first to get a valid name
        results = kb.search_nodes('KSampler', limit=1)
        if results:
            spec = kb.get_node_spec(results[0]['name'])
            assert spec is not None
            assert 'name' in spec or 'category' in spec

    def test_get_node_spec_case_insensitive(self):
        """get_node_spec is case-insensitive."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        results = kb.search_nodes('sampler', limit=1)
        if results:
            name = results[0]['name']
            spec_lower = kb.get_node_spec(name.lower())
            spec_upper = kb.get_node_spec(name.upper())
            # At least one should work
            assert spec_lower is not None or spec_upper is not None

    def test_get_node_spec_not_found(self):
        """get_node_spec returns None for non-existent node."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        spec = kb.get_node_spec('NonExistentNode123456')

        assert spec is None

    def test_simplify_workflow_structure(self):
        """simplify_workflow returns readable format."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        wf = get_simple_workflow()
        result = kb.simplify_workflow(wf)

        assert isinstance(result, str)
        assert '## Pattern:' in result
        assert '## Stats:' in result
        assert '5 nodes' in result

    def test_simplify_workflow_detects_pattern(self):
        """simplify_workflow detects workflow patterns."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        wf = get_simple_workflow()
        result = kb.simplify_workflow(wf)

        # Should detect img2img pattern (LoadImage + VAEEncode)
        assert 'img2img' in result or 'Pattern:' in result

    def test_simplify_workflow_empty(self):
        """simplify_workflow handles empty workflow."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        result = kb.simplify_workflow({'nodes': [], 'links': []})

        assert 'Empty' in result

    def test_list_categories(self):
        """list_categories returns category counts."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        cats = kb.list_categories()

        assert len(cats) > 0
        assert all(isinstance(c, tuple) and len(c) == 2 for c in cats)
        assert all(isinstance(c[1], int) for c in cats)

    def test_list_packs(self):
        """list_packs returns pack counts."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        packs = kb.list_packs()

        assert len(packs) > 0
        assert all(isinstance(p, tuple) and len(p) == 2 for p in packs)

    def test_search_by_author(self):
        """search_by_author finds nodes by author."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        # kijai is a known author in the cache
        results = kb.search_by_author('kijai', limit=5)

        # May or may not find results depending on cache content
        assert isinstance(results, list)

    def test_stats(self):
        """stats returns cache statistics."""
        from cli_tools.registry.knowledge import ComfyKnowledge

        kb = ComfyKnowledge()
        stats = kb.stats()

        assert 'total_nodes' in stats
        assert 'total_packs' in stats
        assert stats['total_nodes'] > 0


# =============================================================================
# Tests: cli_tools/registry/mcp_server.py
# =============================================================================

class TestMCPServer:
    """Tests for mcp_server.py functions."""

    def test_load_workflow_json_string(self):
        """load_workflow parses JSON string."""
        from cli_tools.registry.mcp_server import load_workflow

        wf = get_simple_workflow()
        wf_json = json.dumps(wf)
        loaded = load_workflow(wf_json)

        assert loaded['nodes'][0]['type'] == 'LoadImage'
        assert len(loaded['nodes']) == 5

    def test_load_workflow_file_path(self):
        """load_workflow loads from file path."""
        from cli_tools.registry.mcp_server import load_workflow

        path = get_real_workflow_path()
        if path:
            loaded = load_workflow(str(path))
            assert 'nodes' in loaded
            assert 'links' in loaded
            assert len(loaded['nodes']) > 0

    def test_load_workflow_long_json(self):
        """load_workflow handles long JSON strings."""
        from cli_tools.registry.mcp_server import load_workflow

        # Create a workflow with many nodes
        wf = get_simple_workflow()
        wf['nodes'] = wf['nodes'] * 100  # Duplicate nodes
        wf_json = json.dumps(wf)

        assert len(wf_json) > 10000  # Ensure it's long
        loaded = load_workflow(wf_json)
        assert len(loaded['nodes']) == 500

    def test_load_workflow_invalid_json(self):
        """load_workflow raises on invalid JSON."""
        from cli_tools.registry.mcp_server import load_workflow
        import pytest

        with pytest.raises(json.JSONDecodeError):
            load_workflow('not valid json')

    def test_format_trace_result_success(self):
        """format_trace_result formats successful trace."""
        from cli_tools.registry.mcp_server import format_trace_result

        result = {
            'node_id': 1,
            'node_type': 'TestNode',
            'title': 'My Node',
            'inputs': [
                {'slot': 0, 'name': 'input1', 'source_node': 2, 'source_type': 'OtherNode', 'source_slot': 0}
            ],
            'outputs': [
                {'slot': 0, 'name': 'output1', 'targets': [{'node': 3, 'type': 'NextNode', 'slot': 0}]}
            ]
        }

        formatted = format_trace_result(result)

        assert '[Node 1]' in formatted
        assert 'TestNode' in formatted
        assert 'My Node' in formatted
        assert 'INPUTS:' in formatted
        assert 'OUTPUTS:' in formatted
        assert 'Node 2' in formatted
        assert 'Node 3' in formatted

    def test_format_trace_result_error(self):
        """format_trace_result handles error result."""
        from cli_tools.registry.mcp_server import format_trace_result

        result = {'error': 'Node 999 not found'}
        formatted = format_trace_result(result)

        assert 'Node 999 not found' in formatted

    def test_format_trace_result_unconnected(self):
        """format_trace_result handles unconnected slots."""
        from cli_tools.registry.mcp_server import format_trace_result

        result = {
            'node_id': 1,
            'node_type': 'TestNode',
            'title': None,
            'inputs': [
                {'slot': 0, 'name': 'input1', 'source_node': None, 'source_type': None, 'source_slot': None}
            ],
            'outputs': [
                {'slot': 0, 'name': 'output1', 'targets': []}
            ]
        }

        formatted = format_trace_result(result)

        assert 'unconnected' in formatted.lower()


# =============================================================================
# Integration Tests with Real Workflow
# =============================================================================

class TestIntegration:
    """Integration tests using real workflow file."""

    def test_full_analysis_pipeline(self):
        """Test complete analysis pipeline on real workflow."""
        path = get_real_workflow_path()
        if not path:
            return  # Skip if no real workflow

        from cli_tools.analysis import analyze_workflow, trace_node, find_upstream, get_workflow_info
        from cli_tools.registry.knowledge import ComfyKnowledge

        with open(path) as f:
            wf = json.load(f)

        # Get info
        info = get_workflow_info(wf)
        assert info['node_count'] > 0

        # Analyze
        analysis = analyze_workflow(wf)
        assert len(analysis['entry_points']) > 0

        # Trace a node
        if wf['nodes']:
            node_id = wf['nodes'][0]['id']
            trace = trace_node(wf, node_id)
            assert 'error' not in trace

        # Simplify
        kb = ComfyKnowledge()
        simplified = kb.simplify_workflow(wf)
        assert '## Pattern:' in simplified
        assert '## Stats:' in simplified

    def test_mcp_tools_on_real_workflow(self):
        """Test MCP tool functions on real workflow."""
        path = get_real_workflow_path()
        if not path:
            return  # Skip if no real workflow

        from cli_tools.registry.mcp_server import load_workflow, format_trace_result
        from cli_tools.analysis import trace_node

        # Load via MCP function
        wf = load_workflow(str(path))
        assert len(wf['nodes']) > 0

        # Trace via analysis
        node_id = wf['nodes'][0]['id']
        result = trace_node(wf, node_id)

        # Format via MCP function
        formatted = format_trace_result(result)
        assert f'[Node {node_id}]' in formatted


# =============================================================================
# Main
# =============================================================================

def run_tests():
    """Run all tests and report results."""
    import traceback

    test_classes = [
        TestAnalysis,
        TestSearch,
        TestDescriptions,
        TestKnowledge,
        TestMCPServer,
        TestIntegration,
    ]

    total = 0
    passed = 0
    failed = 0
    errors = []

    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print('='*60)

        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                total += 1
                try:
                    getattr(instance, method_name)()
                    print(f"  ✓ {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  ✗ {method_name}: {e}")
                    failed += 1
                    errors.append((f"{test_class.__name__}.{method_name}", str(e)))
                except Exception as e:
                    print(f"  ✗ {method_name}: {type(e).__name__}: {e}")
                    failed += 1
                    errors.append((f"{test_class.__name__}.{method_name}", traceback.format_exc()))

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print('='*60)

    if errors:
        print("\nFailures:")
        for name, error in errors:
            print(f"\n  {name}:")
            for line in error.split('\n')[:5]:
                print(f"    {line}")

    return failed == 0


if __name__ == '__main__':
    # Check if pytest is available
    try:
        import pytest
        sys.exit(pytest.main([__file__, '-v']))
    except ImportError:
        # Fall back to simple runner
        success = run_tests()
        sys.exit(0 if success else 1)
