"""Node type descriptions."""

import re

# Human-readable descriptions for common node types
NODE_DESCRIPTIONS = {
    # Loaders
    'vhs_loadvideo': 'Load video file',
    'loadimage': 'Load image file',
    'checkpointloadersimple': 'Load model checkpoint',
    'vaeloader': 'Load VAE model',
    'loraloader': 'Load LoRA weights',
    'upscalemodelloader': 'Load upscale model',
    'cliploader': 'Load CLIP text encoder',
    # Samplers
    'ksampler': 'Denoise/generate with sampler',
    'wanvideosampler': 'WanVideo denoising sampler',
    'samplercustom': 'Custom sampler',
    # Encoding/Decoding
    'vaedecode': 'Decode latent to image',
    'vaeencode': 'Encode image to latent',
    'wanvideoencode': 'Encode frames to video latent',
    'wanvideodecode': 'Decode video latent to frames',
    'clipencode': 'Encode text prompt',
    # Image processing
    'imageupscalewithmodel': 'Upscale with AI model',
    'imageupscalewithmodelbatched': 'Upscale batch with AI model',
    'imageresize': 'Resize image',
    'imagesharpen': 'Sharpen image',
    'imagesmartsharp': 'Smart sharpen image',
    # Video
    'vhs_videocombine': 'Combine frames to video',
    'vhs_splitimages': 'Split video to frames',
    # Utility
    'getnode': 'Get variable value',
    'setnode': 'Set variable value',
    'intconstant': 'Integer constant',
    'floatconstant': 'Float constant',
    'stringconstant': 'String constant',
    # Math
    'simplemath': 'Math operation',
    'mathexpression': 'Math expression',
    # Control
    'forloopstart': 'Start of for loop',
    'forloopend': 'End of for loop',
    'whileloopstart': 'Start of while loop',
    'whileloopend': 'End of while loop',
}


def get_node_description(node_type: str) -> str:
    """Get a human-readable description for a node type."""
    normalized = re.sub(r'[^a-z0-9]', '', node_type.lower())

    for key, desc in NODE_DESCRIPTIONS.items():
        if key in normalized or normalized in key:
            return desc

    # Infer from name
    words = re.sub(r'([a-z])([A-Z])', r'\1 \2', node_type)
    words = re.sub(r'[_+|]', ' ', words)
    words = re.sub(r'\s+', ' ', words).strip()

    for suffix in ['Node', 'Loader', 'Simple', 'Advanced', 'pysssss', 'rgthree']:
        words = re.sub(rf'\s*{suffix}\s*$', '', words, flags=re.IGNORECASE)

    return words.lower() if words else node_type
