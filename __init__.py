import os
import sys
import importlib.util

import nodes


impact_modules = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ComfyUI-Impact-Pack", "modules"))
if impact_modules not in sys.path:
    sys.path.append(impact_modules)

from impact import utils

detailer_spec = importlib.util.spec_from_file_location(
    "advanced_detailer_pipe_detailer", os.path.join(os.path.dirname(__file__), "detailer.py"))
detailer_module = importlib.util.module_from_spec(detailer_spec)
sys.modules[detailer_spec.name] = detailer_module
detailer_spec.loader.exec_module(detailer_module)
detailer_do_detail = detailer_module.detailer_do_detail


class AdvancedDetailerDebugPipe:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = nodes.NODE_CLASS_MAPPINGS["DetailerForEachDebugPipe"].INPUT_TYPES()
        required = inputs["required"]
        required.pop("denoise")

        advanced_steps = {
            "start_at_step": ("INT", {"default": 0, "min": 0, "max": 10000, "advanced": True}),
            "end_at_step": ("INT", {"default": 10000, "min": 0, "max": 10000, "advanced": True}),
        }
        ordered = {}
        for name, value in required.items():
            ordered[name] = value
            if name == "steps":
                ordered.update(advanced_steps)
        inputs["required"] = ordered
        return inputs

    RETURN_TYPES = ("IMAGE", "SEGS", "BASIC_PIPE", "IMAGE", "IMAGE", "IMAGE", "IMAGE")
    RETURN_NAMES = ("image", "segs", "basic_pipe", "cropped", "cropped_refined", "cropped_refined_alpha", "cnet_images")
    OUTPUT_IS_LIST = (False, False, False, True, True, True, True)
    FUNCTION = "doit"
    CATEGORY = "ImpactPack/Detailer"
    DESCRIPTION = "It enhances details by inpainting each region within the detected area bundle (SEGS) after enlarging them based on the guide size."

    def doit(self, image, segs, guide_size, guide_size_for, max_size, seed, steps, start_at_step, end_at_step,
             cfg, sampler_name, scheduler, feather, noise_mask, force_inpaint, basic_pipe, wildcard, cycle=1,
             refiner_ratio=None, detailer_hook=None, refiner_basic_pipe_opt=None, inpaint_model=False,
             noise_mask_feather=0, scheduler_func_opt=None, tiled_encode=False, tiled_decode=False):
        if len(image) > 1:
            raise Exception('[Impact Pack] ERROR: DetailerForEach does not allow image batches.\nPlease refer to https://github.com/ltdrdata/ComfyUI-extension-tutorials/blob/Main/ComfyUI-Impact-Pack/tutorial/batching-detailer.md for more information.')

        model, clip, vae, positive, negative = basic_pipe

        if refiner_basic_pipe_opt is None:
            refiner_model, refiner_clip, refiner_positive, refiner_negative = None, None, None, None
        else:
            refiner_model, refiner_clip, _, refiner_positive, refiner_negative = refiner_basic_pipe_opt

        enhanced_img, cropped, cropped_enhanced, cropped_enhanced_alpha, cnet_images, new_segs = \
            detailer_do_detail(
                image, segs, model, clip, vae, guide_size, guide_size_for, max_size, seed, steps, cfg,
                sampler_name, scheduler, positive, negative, feather, noise_mask, force_inpaint,
                wildcard_opt=wildcard, detailer_hook=detailer_hook,
                refiner_ratio=refiner_ratio, refiner_model=refiner_model, refiner_clip=refiner_clip,
                refiner_positive=refiner_positive, refiner_negative=refiner_negative, cycle=cycle,
                inpaint_model=inpaint_model, noise_mask_feather=noise_mask_feather,
                scheduler_func_opt=scheduler_func_opt, tiled_encode=tiled_encode, tiled_decode=tiled_decode,
                start_at_step=start_at_step, end_at_step=end_at_step,
            )

        if len(cropped) == 0:
            cropped = [utils.empty_pil_tensor()]
        if len(cropped_enhanced) == 0:
            cropped_enhanced = [utils.empty_pil_tensor()]
        if len(cropped_enhanced_alpha) == 0:
            cropped_enhanced_alpha = [utils.empty_pil_tensor()]
        if len(cnet_images) == 0:
            cnet_images = [utils.empty_pil_tensor()]

        return enhanced_img, new_segs, basic_pipe, cropped, cropped_enhanced, cropped_enhanced_alpha, cnet_images


NODE_CLASS_MAPPINGS = {
    "AdvancedDetailerDebugPipe": AdvancedDetailerDebugPipe,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedDetailerDebugPipe": "DetailerDebug (SEGS/pipe Advanced)",
}
