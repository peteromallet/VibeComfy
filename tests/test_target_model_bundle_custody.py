"""Canonical publication retains target filenames without download provenance."""
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow_bundle import emit_bundle, load_bundle


def test_target_filename_survives_canonical_source_publication(tmp_path):
    workflow = workflow_from_ready("image/z_image_turbo")
    exact_vae = r"FLUX1\ae.safetensors"
    workflow.set_input("vae", exact_vae)
    workflow.requirements.models = [
        exact_vae if isinstance(item, dict) and item.get("name") == "ae.safetensors" else item
        for item in workflow.requirements.models
    ]
    # The selected filename is attested by a target picker, not by the old
    # default filename's download URL/hash. Other download witnesses remain.
    workflow.metadata["model_assets"] = [
        item for item in workflow.metadata["model_assets"] if item.get("name") != "ae.safetensors"
    ]
    before = workflow.semantic_digest()
    published = emit_bundle(workflow, tmp_path / "workflow.py", {"operation": "authored"})
    loaded = load_bundle(published.python_path, trust=Provenance.USER_CONFIRMED)
    loaded.require_canonical_authority("target model publication regression")
    assert loaded.workflow.semantic_digest() == before
    assert exact_vae in loaded.workflow.requirements.models
    assert len(loaded.workflow.requirements.models) == 3
    assert loaded.workflow.inputs["vae"].value == exact_vae
    api = loaded.workflow.compile("api")
    vae = next(node for node in api.values() if node["class_type"] == "VAELoader")
    assert vae["inputs"]["vae_name"] == exact_vae
