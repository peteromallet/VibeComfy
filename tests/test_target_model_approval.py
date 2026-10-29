"""The canonical bundle gate distinguishes target picker names from model bytes."""
from __future__ import annotations

import copy
import json

import pytest

from vibecomfy.porting.object_info import get_class
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.schema.provider import TargetSchemaProvider
from vibecomfy.workflow_bundle import WorkflowBundleError, load_bundle


EXACT_VAE = r'FLUX1\ae.safetensors'


def target_info(workflow):
    """A synthetic target capture uses pinned schemas and selected model names."""
    data = {}
    for node in workflow.runtime_nodes().values():
        entry = get_class(node.class_type)
        assert entry is not None, node.class_type
        outputs = entry['outputs']
        data[node.class_type] = {
            'input': copy.deepcopy(entry['inputs']),
            'input_order': copy.deepcopy(entry['input_order']),
            'output': [item['type'] for item in outputs],
            'output_name': [item['name'] for item in outputs],
            'output_is_list': [item['is_list'] for item in outputs],
        }
    for cls, field, name in (
        ('UNETLoader', 'unet_name', 'z_image_turbo_bf16.safetensors'),
        ('CLIPLoader', 'clip_name', 'qwen_3_4b.safetensors'),
        ('VAELoader', 'vae_name', 'ae.safetensors'),
    ):
        data[cls]['input']['required'][field] = [[name]]
    return data


def provider(data, **kwargs):
    return TargetSchemaProvider.from_object_info(
        data, server_url='http://target.invalid:8188', **kwargs,
    )


@pytest.mark.parametrize('template_id', ['image/z_image_turbo', 'image/z_image_img2img'])
def test_turbo_compiles_via_canonical_approval_with_exact_graph_bindings(template_id):
    workflow = workflow_from_ready(template_id)
    assert workflow.metadata['unbound_inputs'] == {}
    workflow.set_input('prompt', 'The exact user prompt.')
    data = target_info(workflow)
    target = provider(data, model_availability='target')
    # This is the production canonical bundle boundary, with no registry,
    # presence, approval, or schema gate patched out.
    bundle = load_bundle(workflow)
    record = bundle.compile(schema_provider=target)
    graph = record.api_projection
    loaders = {item['class_type']: item['inputs'] for item in graph.values()}
    assert loaders['UNETLoader']['unet_name'] == 'z_image_turbo_bf16.safetensors'
    assert loaders['CLIPLoader']['clip_name'] == 'qwen_3_4b.safetensors'
    assert loaders['VAELoader']['vae_name'] == 'ae.safetensors'
    assert loaders['ModelSamplingAuraFlow']['shift'] == 3
    assert loaders['KSampler']['steps'] == 8
    assert loaders['KSampler']['cfg'] == 1
    assert loaders['KSampler']['sampler_name'] == 'res_multistep'
    assert loaders['KSampler']['scheduler'] == 'simple'
    positive_id = loaders['KSampler']['positive'][0]
    assert graph[positive_id]['inputs']['text'] == 'The exact user prompt.'
    assert record.api_digest
    record.assert_matches(bundle, api_projection=record.api_projection, ui_projection=record.ui_projection)
    refs = [d for d in target._approval_diagnostics if d['code'] == 'target_model_reference']
    assert len(refs) == 3
    assert all(d['model_bytes_status'] == 'unverified_target_inventory' for d in refs)
    assert all(d['target_schema_digest'] == target._object_info_digest for d in refs)
    assert all('sha256' not in d for d in refs)


def test_literal_backslash_model_name_roundtrips_without_name_repair():
    workflow = workflow_from_ready('image/z_image_turbo')
    workflow.set_input('vae', EXACT_VAE)
    # Remove the old source-backed asset, preserving exact picker authority.
    workflow.metadata['model_assets'] = [
        a for a in workflow.metadata['model_assets'] if a['name'] != 'ae.safetensors'
    ]
    workflow.requirements.models = [
        EXACT_VAE if (a.get('name') if isinstance(a, dict) else a) == 'ae.safetensors' else a
        for a in workflow.requirements.models
    ]
    data = target_info(workflow)
    data['VAELoader']['input']['required']['vae_name'] = [[EXACT_VAE]]
    target = provider(data, model_availability='target')
    record = load_bundle(workflow).compile(schema_provider=target)
    vae = next(n for n in record.api_projection.values() if n['class_type'] == 'VAELoader')
    assert vae['inputs']['vae_name'] == EXACT_VAE
    assert json.loads(record.to_canonical_bytes())['api_projection']['3']['inputs']['vae_name'] == EXACT_VAE
    assert next(d for d in target._approval_diagnostics if d.get('field') == 'vae_name')['value'] == EXACT_VAE


def test_capture_is_detached_and_target_model_mode_is_explicit(tmp_path):
    workflow = workflow_from_ready('image/z_image_turbo')
    data = target_info(workflow)
    target = provider(data, model_availability='target')
    data['UNETLoader']['input']['required']['unet_name'][0].clear()
    assert target.target_model_reference('UNETLoader', 'unet_name', 'z_image_turbo_bf16.safetensors')
    local = provider(target_info(workflow))
    assert not local.target_model_reference('UNETLoader', 'unet_name', 'z_image_turbo_bf16.safetensors')
    with pytest.raises(WorkflowBundleError, match='not present locally'):
        load_bundle(workflow).compile(schema_provider=local, models_root=tmp_path)


@pytest.mark.parametrize('replacement', ['z_image_bf16.safetensors', 'z_image_turbo_bf16-copy.safetensors'])
def test_target_model_gate_rejects_base_or_similar_turbo_filename(replacement):
    workflow = workflow_from_ready('image/z_image_turbo')
    data = target_info(workflow)
    data['UNETLoader']['input']['required']['unet_name'] = [[replacement]]
    with pytest.raises(WorkflowBundleError, match='not advertised by the selected target'):
        load_bundle(workflow).compile(schema_provider=provider(data, model_availability='target'))


def test_target_inventory_does_not_discharge_unbound_authored_model_requirement():
    workflow = workflow_from_ready('image/z_image_turbo')
    workflow.requirements.models.append('unbound-extra-model.safetensors')
    data = target_info(workflow)
    data['VAELoader']['input']['required']['vae_name'][0].append('unbound-extra-model.safetensors')
    with pytest.raises(WorkflowBundleError, match='not locally registered: unbound-extra-model'):
        load_bundle(workflow).compile(schema_provider=provider(data, model_availability='target'))


def test_original_z_image_template_remains_base():
    graph = workflow_from_ready('image/z_image').compile('api')
    unet = next(n for n in graph.values() if n['class_type'] == 'UNETLoader')
    assert unet['inputs']['unet_name'] == 'z_image_bf16.safetensors'


def test_target_model_mode_does_not_approve_stale_bundle_revision():
    workflow = workflow_from_ready('image/z_image_turbo')
    target = provider(target_info(workflow), model_availability='target')
    bundle = load_bundle(workflow)
    workflow.set_input('prompt', 'Changed after the bundle revision was captured.')
    with pytest.raises(WorkflowBundleError, match='revision is stale'):
        bundle.compile(schema_provider=target)


def test_target_model_mode_still_requires_full_schema_validation():
    workflow = workflow_from_ready('image/z_image_turbo')
    data = target_info(workflow)
    data['KSampler']['input']['required']['sampler_name'] = [['euler']]
    with pytest.raises(WorkflowBundleError, match='sampler_name'):
        load_bundle(workflow).compile(schema_provider=provider(data, model_availability='target'))


def test_final_reconciliation_refreshes_through_the_same_target_transport(monkeypatch):
    import asyncio

    from vibecomfy.runtime.reconciliation import reconcile_before_queue_async
    import vibecomfy.schema.provider as provider_module

    workflow = workflow_from_ready('image/z_image_turbo')
    data = target_info(workflow)
    refreshed = copy.deepcopy(data)
    refreshed['UNETLoader']['input']['required']['unet_name'] = [['z_image_bf16.safetensors']]
    captures = []

    def capture():
        captures.append('same-target-client')
        return refreshed

    def forbidden_client(*_args, **_kwargs):
        raise AssertionError('external captures must retain the caller target transport')

    monkeypatch.setattr(provider_module, 'ComfyClient', forbidden_client)
    target = provider(data, model_availability='target', refresh_object_info=capture)
    old_digest = target._object_info_digest
    bundle = load_bundle(workflow)
    bundle.compile(schema_provider=target)
    reconciliation = asyncio.run(reconcile_before_queue_async(
        bundle, target_schema_provider=target, publish=False,
    ))
    assert captures == ['same-target-client']
    assert target._object_info_digest != old_digest
    assert reconciliation.schema['digest'] == target._object_info_digest
    with pytest.raises(WorkflowBundleError, match='not advertised by the selected target'):
        reconciliation.bundle.compile(schema_provider=target)


def test_external_capture_without_refresh_callback_cannot_reuse_stale_queue_evidence():
    import asyncio

    from vibecomfy.schema.provider import SchemaProviderError

    workflow = workflow_from_ready('image/z_image_turbo')
    target = provider(target_info(workflow), model_availability='target')
    with pytest.raises(SchemaProviderError, match='refresh_object_info'):
        asyncio.run(target.object_info_async())
