import comfy.samplers
import nodes
from comfy_api.latest import io
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


class AdvancedUltimateSDUpscaleNoUpscale(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="AdvancedUltimateSDUpscaleNoUpscale",
            display_name="Ultimate SD Upscale (No Upscale, Advanced Steps)",
            category="image/upscaling",
            description="Runs image-to-image on tiles without upscaling, with explicit start and end sampling steps.",
            inputs=[
                io.Image.Input("upscaled_image"),
                io.Model.Input("model"),
                io.Conditioning.Input("positive"),
                io.Conditioning.Input("negative"),
                io.Vae.Input("vae"),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff, control_after_generate=True),
                io.Int.Input("steps", default=20, min=1, max=10000),
                io.Int.Input("start_at_step", default=0, min=0, max=10000, advanced=True),
                io.Int.Input("end_at_step", default=10000, min=0, max=10000, advanced=True),
                io.Float.Input("cfg", default=8.0, min=0.0, max=100.0),
                io.Combo.Input("sampler_name", options=comfy.samplers.KSampler.SAMPLERS),
                io.Combo.Input("scheduler", options=comfy.samplers.KSampler.SCHEDULERS),
                io.Combo.Input("mode_type", options=["Linear", "Chess", "None"]),
                io.Int.Input("tile_width", default=512, min=64, max=8192, step=8),
                io.Int.Input("tile_height", default=512, min=64, max=8192, step=8),
                io.Int.Input("mask_blur", default=8, min=0, max=64),
                io.Int.Input("tile_padding", default=32, min=0, max=8192, step=8),
                io.Combo.Input("seam_fix_mode", options=["None", "Band Pass", "Half Tile", "Half Tile + Intersections"]),
                io.Float.Input("seam_fix_denoise", default=1.0, min=0.0, max=1.0, step=0.01),
                io.Int.Input("seam_fix_width", default=64, min=0, max=8192, step=8),
                io.Int.Input("seam_fix_mask_blur", default=8, min=0, max=64),
                io.Int.Input("seam_fix_padding", default=16, min=0, max=8192, step=8),
                io.Boolean.Input("force_uniform_tiles", default=True),
                io.Boolean.Input("tiled_decode", default=False),
                io.Int.Input("batch_size", default=1, min=1, max=4096),
            ],
            outputs=[io.Image.Output(tooltip="The final refined image.")],
        )

    @classmethod
    def execute(cls, upscaled_image, model, positive, negative, vae, seed, steps,
                start_at_step, end_at_step, cfg, sampler_name, scheduler,
                mode_type, tile_width, tile_height, mask_blur, tile_padding,
                seam_fix_mode, seam_fix_denoise, seam_fix_mask_blur,
                seam_fix_width, seam_fix_padding, force_uniform_tiles, tiled_decode, batch_size=1):
        result = AdvancedUltimateSDUpscale().upscale(
            image=upscaled_image, model=model, positive=positive, negative=negative, vae=vae,
            upscale_by=1.0, upscale_model=None, seed=seed, steps=steps,
            start_at_step=start_at_step, end_at_step=end_at_step, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler, mode_type=mode_type,
            tile_width=tile_width, tile_height=tile_height, mask_blur=mask_blur, tile_padding=tile_padding,
            seam_fix_mode=seam_fix_mode, seam_fix_denoise=seam_fix_denoise,
            seam_fix_mask_blur=seam_fix_mask_blur, seam_fix_width=seam_fix_width,
            seam_fix_padding=seam_fix_padding, force_uniform_tiles=force_uniform_tiles,
            tiled_decode=tiled_decode, batch_size=batch_size,
        )
        return io.NodeOutput(*result)


NODE_CLASS_MAPPINGS = {
    "AdvancedUltimateSDUpscale": AdvancedUltimateSDUpscale,
    "AdvancedUltimateSDUpscaleNoUpscale": AdvancedUltimateSDUpscaleNoUpscale,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AdvancedUltimateSDUpscale": "Ultimate SD Upscale (Advanced Steps)",
    "AdvancedUltimateSDUpscaleNoUpscale": "Ultimate SD Upscale (No Upscale, Advanced Steps)",
}
