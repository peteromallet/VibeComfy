from __future__ import annotations

"""Identity-independent contract for the canonical LTX first/last workflow."""

from collections.abc import Iterable
from typing import Any

from vibecomfy.contracts.validation import ContractReport
from vibecomfy.lens.core import WorkflowLens
from vibecomfy.workflow import VibeNode, VibeWorkflow

_CHECKPOINT = "ltx-2.3-22b-distilled-fp8.safetensors"
_SIGMAS = "1.,0.99375,0.9875,0.98125,0.975,0.909375,0.725,0.421875,0.0"
_INPUT_ROLES = {
    "seed": ("RandomNoise", "noise_seed"),
    "model": ("LTXAVTextEncoderLoader", "ckpt_name"),
    "prompt": ("CLIPTextEncode", "text"),
    "image": ("LoadImage", "image"),
    "input_image": ("LoadImage", "image"),
    "frames": ("EmptyLTXVLatentVideo", "length"),
    "fps": ("CreateVideo", "fps"),
}
_FORBIDDEN = frozenset(
    {
        "LTXICLoRALoaderModelOnly",
        "LTXAddVideoICLoRAGuide",
        "LTX2MemoryEfficientSageAttentionPatch",
        "LTX2SamplingPreviewOverride",
        "PathchSageAttentionKJ",
    }
)


class LTXFirstLastTwoStageContract:
    """Validate semantic roles and wiring without treating node ids as authority."""

    def __init__(self, workflow: VibeWorkflow) -> None:
        self._workflow = workflow
        self._lens = WorkflowLens(workflow)

    def validate(self) -> ContractReport:
        report = ContractReport("ltx-first-last-two-stage", True)
        self._check_named_inputs(report)
        text_loader = self._one(report, "text_encoder_loader", "LTXAVTextEncoderLoader")
        checkpoint = self._one(report, "checkpoint_loader", "CheckpointLoaderSimple")
        conditioning = self._one(report, "conditioning", "LTXVConditioning")
        empty_latent = self._one(report, "empty_latent", "EmptyLTXVLatentVideo")
        first, last = self._guides(report, empty_latent)
        self._check_loaders(report, text_loader, checkpoint)
        self._check_prompts(report, text_loader, conditioning)
        self._check_guides(report, first, last, conditioning, checkpoint)
        self._check_images(report, first, last)
        self._check_shape(report, empty_latent)
        self._check_sampling(report, last, checkpoint)
        self._check_output(report)
        self._check_forbidden(report)
        return report

    def _nodes(self, class_type: str) -> list[VibeNode]:
        return [node for node in self._workflow.nodes.values() if node.class_type == class_type]

    def _one(
        self,
        report: ContractReport,
        role: str,
        class_type: str,
        candidates: Iterable[VibeNode] | None = None,
    ) -> VibeNode | None:
        found = list(self._nodes(class_type) if candidates is None else candidates)
        if len(found) == 1:
            return found[0]
        report.add(
            f"missing_{role}" if not found else f"ambiguous_{role}",
            f"Expected one {class_type} for {role}, found {len(found)}.",
            detail={"role": role, "class_type": class_type, "node_ids": sorted(node.id for node in found)},
        )
        return None

    def _matches(self, target: VibeNode | None, field: str, source: VibeNode | None, slot: int) -> bool:
        if target is None or source is None:
            return False
        edge = self._lens.edge_source(target.id, field)
        return edge is not None and edge.node_id == source.id and edge.output_slot == slot

    def _edge(
        self,
        report: ContractReport,
        code: str,
        target: VibeNode | None,
        field: str,
        source: VibeNode | None,
        slot: int,
    ) -> None:
        if target is None or source is None:
            return
        actual = self._lens.edge_source(target.id, field)
        if actual is None or actual.node_id != source.id or actual.output_slot != slot:
            report.add(
                code,
                f"{target.class_type}.{field} must consume {source.class_type} output {slot}.",
                detail={
                    "target_node_id": target.id,
                    "target_field": field,
                    "expected_source_node_id": source.id,
                    "expected_output_slot": slot,
                    "actual_source_node_id": getattr(actual, "node_id", None),
                    "actual_output_slot": getattr(actual, "output_slot", None),
                },
            )

    def _upstream(
        self,
        report: ContractReport,
        role: str,
        target: VibeNode | None,
        field: str,
        class_type: str,
        slot: int = 0,
    ) -> VibeNode | None:
        actual = self._lens.edge_source(target.id, field) if target else None
        node = self._lens.node(actual.node_id) if actual and actual.node_id else None
        if node is None or node.class_type != class_type or actual.output_slot != slot:
            report.add(
                f"wrong_{role}",
                f"{getattr(target, 'class_type', 'missing')}.{field} must consume {class_type} output {slot}.",
                detail={
                    "actual_source_node_id": getattr(actual, "node_id", None),
                    "actual_output_slot": getattr(actual, "output_slot", None),
                    "actual_class_type": getattr(node, "class_type", None),
                },
            )
            return None
        return node

    def _check_named_inputs(self, report: ContractReport) -> None:
        missing = set(_INPUT_ROLES) - set(self._workflow.inputs)
        if missing:
            report.add("missing_named_inputs", f"Missing named inputs: {sorted(missing)}", detail={"missing": sorted(missing)})
        for name, (class_type, field) in _INPUT_ROLES.items():
            target = self._lens.registered_input_target(name)
            if target is None:
                continue
            node = self._lens.node(target.node_id)
            if node is None or node.class_type != class_type or target.field != field:
                report.add(
                    "wrong_named_input_target",
                    f"Named input {name!r} must target {class_type}.{field}.",
                    detail={"input": name, "actual_node_id": target.node_id, "actual_field": target.field},
                )
        image = self._lens.registered_input_target("image")
        alias = self._lens.registered_input_target("input_image")
        if image and alias and (image.node_id, image.field) != (alias.node_id, alias.field):
            report.add("split_image_alias", "image and input_image must target the same LoadImage field.")

    def _check_loaders(
        self, report: ContractReport, text_loader: VibeNode | None, checkpoint: VibeNode | None
    ) -> None:
        for role, node in (("text encoder", text_loader), ("checkpoint", checkpoint)):
            if node is None:
                continue
            actual = self._lens.node_value(node.id, "ckpt_name")
            if actual != _CHECKPOINT:
                report.add(
                    "wrong_distilled_checkpoint",
                    f"The {role} loader uses {actual!r}, expected {_CHECKPOINT!r}.",
                    detail={"node_id": node.id, "actual": actual, "expected": _CHECKPOINT},
                )

    def _guides(
        self, report: ContractReport, empty_latent: VibeNode | None
    ) -> tuple[VibeNode | None, VibeNode | None]:
        guides = self._nodes("LTXVAddGuide")
        if len(guides) != 2:
            report.add(
                "missing_first_strength_guide" if not guides else "ambiguous_first_strength_guide",
                f"Expected exactly two LTXVAddGuide nodes, found {len(guides)}.",
                detail={"node_ids": sorted(node.id for node in guides)},
            )
            if len(guides) < 2:
                report.add("missing_last_strength_guide", "Missing the chained last-frame LTXVAddGuide role.")
        first = self._one(
            report,
            "first_strength_guide",
            "LTXVAddGuide",
            [node for node in guides if self._matches(node, "latent", empty_latent, 0)],
        )
        last = self._one(
            report,
            "last_strength_guide",
            "LTXVAddGuide",
            [node for node in guides if node is not first and self._matches(node, "latent", first, 2)],
        )
        return first, last

    def _check_prompts(
        self,
        report: ContractReport,
        text_loader: VibeNode | None,
        conditioning: VibeNode | None,
    ) -> None:
        resolved: dict[str, VibeNode | None] = {}
        for label in ("positive", "negative"):
            resolved[label] = self._upstream(report, f"{label}_encode", conditioning, label, "CLIPTextEncode", 0)
            self._edge(report, f"wrong_{label}_clip_source", resolved[label], "clip", text_loader, 0)
        encoders = self._nodes("CLIPTextEncode")
        if len(encoders) != 2 or (
            resolved["positive"] is not None
            and resolved["negative"] is not None
            and resolved["positive"].id == resolved["negative"].id
        ):
            report.add("ambiguous_prompt_encoders", "Positive and negative must resolve to two distinct CLIPTextEncode nodes.")
        prompt = self._lens.registered_input_target("prompt")
        if prompt and (resolved["positive"] is None or prompt.node_id != resolved["positive"].id):
            report.add("wrong_prompt_binding", "prompt must target the CLIPTextEncode role feeding positive conditioning.")

    def _check_guides(
        self,
        report: ContractReport,
        first: VibeNode | None,
        last: VibeNode | None,
        conditioning: VibeNode | None,
        checkpoint: VibeNode | None,
    ) -> None:
        for label, node in (("first", first), ("last", last)):
            if node is not None:
                strength = self._lens.node_value(node.id, "strength")
                if strength is not None and (
                    not isinstance(strength, (int, float)) or isinstance(strength, bool) or not 0 <= float(strength) <= 1
                ):
                    report.add(f"{label}_strength_out_of_range", f"{label} guide strength must be in [0, 1].")
        self._edge(report, "wrong_first_guide_positive_source", first, "positive", conditioning, 0)
        self._edge(report, "wrong_first_guide_negative_source", first, "negative", conditioning, 1)
        self._edge(report, "wrong_first_guide_vae_source", first, "vae", checkpoint, 2)
        self._edge(report, "wrong_last_guide_positive_source", last, "positive", first, 0)
        self._edge(report, "wrong_last_guide_negative_source", last, "negative", first, 1)
        self._edge(report, "wrong_last_guide_vae_source", last, "vae", checkpoint, 2)
        if last is not None and self._lens.node_value(last.id, "frame_idx") != -1:
            report.add("wrong_last_guide_frame_index", "The last-frame guide must retain frame_idx=-1.")
        guider = self._one(report, "cfg_guider", "CFGGuider")
        self._edge(report, "wrong_guider_model_source", guider, "model", checkpoint, 0)
        self._edge(report, "wrong_guider_positive_source", guider, "positive", last, 0)
        self._edge(report, "wrong_guider_negative_source", guider, "negative", last, 1)

    def _check_images(self, report: ContractReport, first: VibeNode | None, last: VibeNode | None) -> None:
        loads: list[VibeNode | None] = []
        for label, guide in (("first_image", first), ("last_image", last)):
            preprocess = self._upstream(report, f"{label}_preprocess", guide, "image", "LTXVPreprocess")
            resize = self._upstream(report, f"{label}_resize", preprocess, "image", "ResizeImageMaskNode")
            loads.append(self._upstream(report, f"{label}_load", resize, "input", "LoadImage"))
        if loads[0] is not None and loads[1] is not None and loads[0].id == loads[1].id:
            report.add("ambiguous_first_last_images", "First and last guide paths must use distinct LoadImage nodes.")
        public_image = self._lens.registered_input_target("image")
        if public_image and loads[0] and public_image.node_id != loads[0].id:
            report.add("wrong_first_image_binding", "The public image input must target the first guide path.")

    def _check_shape(self, report: ContractReport, empty_latent: VibeNode | None) -> None:
        resizes = self._nodes("ResizeImageMaskNode")
        if len(resizes) != 2:
            report.add("ambiguous_resize_nodes", f"Expected two ResizeImageMaskNode roles, found {len(resizes)}.")
        dimensions: list[tuple[Any, Any]] = []
        for node in resizes:
            pair = (
                self._lens.node_value(node.id, "resize_type.width"),
                self._lens.node_value(node.id, "resize_type.height"),
            )
            dimensions.append(pair)
            for label, value in zip(("width", "height"), pair):
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    report.add(f"invalid_{label}", f"Resize {label} must be a positive integer, got {value!r}.")
        if len(dimensions) == 2 and dimensions[0] != dimensions[1]:
            report.add("mismatched_guide_dimensions", "The first and last guide dimensions must match.")
        if empty_latent:
            frames = self._lens.node_value(empty_latent.id, "length")
            if not isinstance(frames, int) or isinstance(frames, bool) or frames <= 0:
                report.add("invalid_frame_count", f"Frame count must be a positive integer, got {frames!r}.")
        create_video = self._one(report, "create_video", "CreateVideo")
        if create_video:
            fps = self._lens.node_value(create_video.id, "fps")
            if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0:
                report.add("invalid_fps", f"FPS must be positive, got {fps!r}.")

    def _check_sampling(
        self, report: ContractReport, last: VibeNode | None, checkpoint: VibeNode | None
    ) -> None:
        roles = {
            "sampler": self._one(report, "sampler", "SamplerCustomAdvanced"),
            "guider": self._one(report, "sampler_guider", "CFGGuider"),
            "latent_image": self._one(report, "concat_av_latent", "LTXVConcatAVLatent"),
            "noise": self._one(report, "noise", "RandomNoise"),
            "sampler_kind": self._one(report, "sampler_kind", "SamplerEulerAncestral"),
            "sigmas": self._one(report, "sigmas", "ManualSigmas"),
        }
        self._edge(report, "wrong_concat_latent_source", roles["latent_image"], "video_latent", last, 2)
        for field in ("guider", "latent_image", "noise", "sigmas"):
            self._edge(report, f"wrong_sampler_{field}_source", roles["sampler"], field, roles[field], 0)
        self._edge(report, "wrong_sampler_sampler_source", roles["sampler"], "sampler", roles["sampler_kind"], 0)
        sigmas = roles["sigmas"]
        if sigmas:
            actual = self._lens.node_value(sigmas.id, "sigmas") or self._lens.node_value(sigmas.id, "widget_0")
            if str(actual).replace(" ", "") != _SIGMAS:
                report.add("wrong_sigmas_value", f"ManualSigmas value is {actual!r}.")

        separate = self._one(report, "separate_av_latent", "LTXVSeparateAVLatent")
        crop = self._one(report, "crop_guides", "LTXVCropGuides")
        decode = self._one(report, "video_decode", "VAEDecodeTiled")
        self._edge(report, "wrong_separate_latent_source", separate, "av_latent", roles["sampler"], 1)
        self._edge(report, "wrong_crop_latent_source", crop, "latent", separate, 0)
        self._edge(report, "wrong_decode_samples_source", decode, "samples", crop, 2)
        self._edge(report, "wrong_decode_vae_source", decode, "vae", checkpoint, 2)

    def _check_output(self, report: ContractReport) -> None:
        outputs = [output for output in self._workflow.outputs if output.output_type == "SaveVideo"]
        saves = self._nodes("SaveVideo")
        if len(outputs) != 1 or len(saves) != 1 or outputs[0].node_id != saves[0].id:
            report.add(
                "missing_savevideo_output" if not outputs else "ambiguous_savevideo_output",
                "Exactly one SaveVideo node must be registered as the video output.",
            )
            return
        create_video = self._one(report, "output_create_video", "CreateVideo")
        video_decode = self._one(report, "output_video_decode", "VAEDecodeTiled")
        audio_decode = self._one(report, "output_audio_decode", "LTXVAudioVAEDecode")
        self._edge(report, "wrong_createvideo_images_source", create_video, "images", video_decode, 0)
        self._edge(report, "wrong_createvideo_audio_source", create_video, "audio", audio_decode, 0)
        self._edge(report, "wrong_savevideo_source", saves[0], "video", create_video, 0)

    def _check_forbidden(self, report: ContractReport) -> None:
        found = sorted(
            f"{node.class_type}:{node_id}"
            for node_id, node in self._workflow.nodes.items()
            if node.class_type in _FORBIDDEN
        )
        if found:
            report.add("incompatible_nodes_present", f"Incompatible nodes present: {found}", detail={"found": found})
        bad_packs = set(self._workflow.requirements.custom_nodes) & {"rgthree-comfy"}
        if bad_packs:
            report.add("incompatible_custom_nodes_declared", f"Incompatible packs: {sorted(bad_packs)}")
