# Add Save Node and Finalize

Start with a workflow that loads a checkpoint ("sd_xl_base_1.0.safetensors") and an input image ("input/source.png"), then add a save-image block wired to the loaded image output. Finalize the workflow metadata after adding the save node, and give me the output path. I want to confirm the finalization picked up the save node and the checkpoint model.
