import comfy.samplers
import nodes
from impact import impact_sampling


class AdvancedUltimateSDUpscale:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = nodes.NODE_CLASS_MAPPINGS["UltimateSDUpscale"].INPUT_TYPES()
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

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "upscale"
    CATEGORY = "image/upscaling"
    OUTPUT_TOOLTIPS = ("The final upscaled image.",)
    DESCRIPTION = "Upscales an image and runs image-to-image on tiles with explicit start and end sampling steps."

    def upscale(self, image, model, positive, negative, vae, upscale_by, seed, steps,
                start_at_step, end_at_step, cfg, sampler_name, scheduler, upscale_model,
                mode_type, tile_width, tile_height, mask_blur, tile_padding,
                seam_fix_mode, seam_fix_denoise, seam_fix_mask_blur,
                seam_fix_width, seam_fix_padding, force_uniform_tiles, tiled_decode, batch_size=1):
        sigmas = impact_sampling.calculate_sigmas(model, sampler_name, scheduler, steps)
        end_at_step = min(end_at_step, len(sigmas) - 1)

        usdu_node = nodes.NODE_CLASS_MAPPINGS["UltimateSDUpscale"]()
        if start_at_step >= end_at_step:
            return usdu_node.upscale(
                image, model, positive, negative, vae, upscale_by, seed,
                steps, cfg, sampler_name, scheduler, 0.0, upscale_model,
                mode_type, tile_width, tile_height, mask_blur, tile_padding,
                seam_fix_mode, seam_fix_denoise, seam_fix_mask_blur,
                seam_fix_width, seam_fix_padding, force_uniform_tiles, tiled_decode, batch_size,
            )

        sigmas = sigmas[start_at_step:end_at_step + 1].clone()
        sigmas[-1] = 0

        return usdu_node.upscale(
            image, model, positive, negative, vae, upscale_by, seed,
            steps, cfg, sampler_name, scheduler, 1.0, upscale_model,
            mode_type, tile_width, tile_height, mask_blur, tile_padding,
            seam_fix_mode, seam_fix_denoise, seam_fix_mask_blur,
            seam_fix_width, seam_fix_padding, force_uniform_tiles, tiled_decode, batch_size,
            custom_sampler=comfy.samplers.sampler_object(sampler_name), custom_sigmas=sigmas,
        )


NODE_CLASS_MAPPINGS = {
    "AdvancedUltimateSDUpscale": AdvancedUltimateSDUpscale,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedUltimateSDUpscale": "Ultimate SD Upscale (Advanced Steps)",
}
