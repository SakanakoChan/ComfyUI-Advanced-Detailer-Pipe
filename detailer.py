# Adapted from ComfyUI-Impact-Pack's detailer implementation (GPL-3.0).
import inspect
import logging
import math
import time

import nodes
import torch
import impact.wildcards as wildcards
from impact import core, impact_sampling, utils
from impact.core import SEG


def enhance_detail(image, model, clip, vae, guide_size, guide_size_for_bbox, max_size, bbox, seed, steps, cfg,
                   sampler_name, scheduler, positive, negative, noise_mask, force_inpaint,
                   wildcard_opt=None, wildcard_opt_concat_mode=None, detailer_hook=None,
                   refiner_ratio=None, refiner_model=None, refiner_clip=None, refiner_positive=None,
                   refiner_negative=None, control_net_wrapper=None, cycle=1,
                   inpaint_model=False, noise_mask_feather=0, scheduler_func=None,
                   vae_tiled_encode=False, vae_tiled_decode=False, start_at_step=0, end_at_step=10000):
    if noise_mask is not None:
        noise_mask = utils.tensor_gaussian_blur_mask(noise_mask, noise_mask_feather)
        noise_mask = noise_mask.squeeze(3)

        if noise_mask_feather > 0 and 'denoise_mask_function' not in model.model_options:
            model = utils.apply_differential_diffusion(model)

    if wildcard_opt is not None and wildcard_opt != "":
        model, _, wildcard_positive = wildcards.process_with_loras(wildcard_opt, model, clip)

        if wildcard_opt_concat_mode == "concat":
            positive = nodes.ConditioningConcat().concat(positive, wildcard_positive)[0]
        else:
            positive = wildcard_positive
            positive = [positive[0].copy()]
            if 'pooled_output' in wildcard_positive[0][1]:
                positive[0][1]['pooled_output'] = wildcard_positive[0][1]['pooled_output']
            elif 'pooled_output' in positive[0][1]:
                del positive[0][1]['pooled_output']

    h = image.shape[1]
    w = image.shape[2]
    bbox_h = bbox[3] - bbox[1]
    bbox_w = bbox[2] - bbox[0]

    if not force_inpaint and bbox_h >= guide_size and bbox_w >= guide_size:
        logging.info("Detailer: segment skip (enough big)")
        return None, None

    if guide_size_for_bbox:
        upscale = guide_size / min(bbox_w, bbox_h)
    else:
        upscale = guide_size / min(w, h)

    new_w = int(w * upscale)
    new_h = int(h * upscale)

    if 'aitemplate_keep_loaded' in model.model_options:
        max_size = min(4096, max_size)

    if new_w > max_size or new_h > max_size:
        upscale *= max_size / max(new_w, new_h)
        new_w = int(w * upscale)
        new_h = int(h * upscale)

    if not force_inpaint:
        if upscale <= 1.0:
            logging.info(f"Detailer: segment skip [determined upscale factor={upscale}]")
            return None, None

        if new_w == 0 or new_h == 0:
            logging.info(f"Detailer: segment skip [zero size={new_w, new_h}]")
            return None, None
    elif upscale <= 1.0 or new_w == 0 or new_h == 0:
        logging.info("Detailer: force inpaint")
        upscale = 1.0
        new_w = w
        new_h = h

    if detailer_hook is not None:
        new_w, new_h = detailer_hook.touch_scaled_size(new_w, new_h)

    logging.info(f"Detailer: segment upscale for ({bbox_w, bbox_h}) | crop region {w, h} x {upscale} -> {new_w, new_h}")

    upscaled_image = utils.tensor_resize(image, new_w, new_h)

    if detailer_hook is not None:
        upscaled_image = detailer_hook.post_upscale(upscaled_image, noise_mask)

    cnet_pils = None
    if control_net_wrapper is not None:
        positive, negative, cnet_pils = control_net_wrapper.apply(positive, negative, upscaled_image, noise_mask)
        model, cnet_pils2 = control_net_wrapper.doit_ipadapter(model)
        cnet_pils.extend(cnet_pils2)

    if detailer_hook is None or not detailer_hook.get_skip_sampling():
        if noise_mask is not None and inpaint_model:
            imc_encode = nodes.InpaintModelConditioning().encode
            if 'noise_mask' in inspect.signature(imc_encode).parameters:
                positive, negative, latent_image = imc_encode(positive, negative, upscaled_image, vae, mask=noise_mask, noise_mask=True)
            else:
                logging.warning("[Impact Pack] ComfyUI is an outdated version.")
                positive, negative, latent_image = imc_encode(positive, negative, upscaled_image, vae, noise_mask)
        else:
            latent_image = utils.to_latent_image(upscaled_image, vae, vae_tiled_encode=vae_tiled_encode)
            if noise_mask is not None:
                latent_image['noise_mask'] = noise_mask

        if detailer_hook is not None:
            latent_image = detailer_hook.post_encode(latent_image)

        refined_latent = latent_image
        sampler_opt = detailer_hook.get_custom_sampler() if detailer_hook is not None else None

        for i in range(cycle):
            if detailer_hook is not None:
                detailer_hook.set_steps((i, cycle))
                refined_latent = detailer_hook.cycle_latent(refined_latent)
                model2, seed2, steps2, cfg2, sampler_name2, scheduler2, positive2, negative2, _, _ = \
                    detailer_hook.pre_ksample(model, seed + i, steps, cfg, sampler_name, scheduler,
                                              positive, negative, latent_image, 1.0)
                noise, is_touched = detailer_hook.get_custom_noise(
                    seed + i, torch.zeros(latent_image['samples'].size()), is_touched=False)
                if not is_touched:
                    noise = None
            else:
                model2, seed2, steps2, cfg2, sampler_name2, scheduler2, positive2, negative2 = \
                    model, seed + i, steps, cfg, sampler_name, scheduler, positive, negative
                noise = None

            if (refiner_ratio is None or refiner_model is None or refiner_clip is None
                    or refiner_positive is None or refiner_negative is None):
                refined_latent = impact_sampling.separated_sample(
                    model2, True, seed2, steps2, cfg2, sampler_name2, scheduler2, positive2, negative2,
                    refined_latent, start_at_step, end_at_step, False, sampler_opt=sampler_opt,
                    noise=noise, scheduler_func=scheduler_func)
            else:
                final_step = min(steps2, end_at_step)
                if start_at_step >= final_step:
                    continue

                refiner_start = start_at_step + math.floor((final_step - start_at_step) * (1.0 - refiner_ratio))
                temp_latent = impact_sampling.separated_sample(
                    model2, True, seed2, steps2, cfg2, sampler_name2, scheduler2, positive2, negative2,
                    refined_latent, start_at_step, refiner_start, True, sampler_opt=sampler_opt,
                    noise=noise, scheduler_func=scheduler_func)

                if 'noise_mask' in latent_image:
                    compositor = nodes.NODE_CLASS_MAPPINGS['LatentCompositeMasked']()
                    temp_latent = compositor.composite(latent_image, temp_latent, 0, 0, False, latent_image['noise_mask'])[0]

                refined_latent = impact_sampling.separated_sample(
                    refiner_model, False, seed2, steps2, cfg2, sampler_name2, scheduler2,
                    refiner_positive, refiner_negative, temp_latent, refiner_start, final_step, False,
                    sampler_opt=sampler_opt, scheduler_func=scheduler_func)

        if detailer_hook is not None:
            refined_latent = detailer_hook.pre_decode(refined_latent)

        start = time.time()
        if vae_tiled_decode:
            (refined_image,) = nodes.VAEDecodeTiled().decode(vae, refined_latent, 512)
            logging.info(f"[Impact Pack] vae decoded (tiled) in {time.time() - start:.1f}s")
        else:
            try:
                refined_image = vae.decode(refined_latent['samples'])
            except Exception:
                logging.warning(f"[Impact Pack] failed after {time.time() - start:.1f}s, doing vae.decode_tiled 64...")
                refined_image = vae.decode_tiled(refined_latent["samples"], tile_x=64, tile_y=64)
            logging.info(f"[Impact Pack] vae decoded in {time.time() - start:.1f}s")
    else:
        refined_image = upscaled_image

    if detailer_hook is not None:
        refined_image = detailer_hook.post_decode(refined_image)

    if len(refined_image.shape) == 5:
        refined_image = refined_image.squeeze(0)

    refined_image = utils.tensor_resize(refined_image, w, h).cpu()
    return refined_image, cnet_pils


def detailer_do_detail(image, segs, model, clip, vae, guide_size, guide_size_for_bbox, max_size, seed, steps, cfg,
                       sampler_name, scheduler, positive, negative, feather, noise_mask, force_inpaint,
                       wildcard_opt=None, detailer_hook=None, refiner_ratio=None, refiner_model=None,
                       refiner_clip=None, refiner_positive=None, refiner_negative=None, cycle=1,
                       inpaint_model=False, noise_mask_feather=0, scheduler_func_opt=None,
                       tiled_encode=False, tiled_decode=False, start_at_step=0, end_at_step=10000):
    if len(image) > 1:
        raise Exception('[Impact Pack] ERROR: DetailerForEach does not allow image batches.\nPlease refer to https://github.com/ltdrdata/ComfyUI-extension-tutorials/blob/Main/ComfyUI-Impact-Pack/tutorial/batching-detailer.md for more information.')

    image = image.clone()
    enhanced_alpha_list = []
    enhanced_list = []
    cropped_list = []
    cnet_pil_list = []

    segs = core.segs_scale_match(segs, image.shape)
    new_segs = []

    wildcard_concat_mode = None
    if wildcard_opt is not None:
        if wildcard_opt.startswith('[CONCAT]'):
            wildcard_concat_mode = 'concat'
            wildcard_opt = wildcard_opt[8:]
        wmode, wildcard_chooser = wildcards.process_wildcard_for_segs(wildcard_opt)
    else:
        wmode, wildcard_chooser = None, None

    if wmode in ['ASC', 'DSC', 'ASC-SIZE', 'DSC-SIZE']:
        if wmode == 'ASC':
            ordered_segs = sorted(segs[1], key=lambda x: (x.bbox[0], x.bbox[1]))
        elif wmode == 'DSC':
            ordered_segs = sorted(segs[1], key=lambda x: (x.bbox[0], x.bbox[1]), reverse=True)
        elif wmode == 'ASC-SIZE':
            ordered_segs = sorted(segs[1], key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
        else:
            ordered_segs = sorted(segs[1], key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]), reverse=True)
    else:
        ordered_segs = segs[1]

    if not (isinstance(model, str) and model == "DUMMY") and noise_mask_feather > 0 and 'denoise_mask_function' not in model.model_options:
        model = utils.apply_differential_diffusion(model)

    for i, seg in enumerate(ordered_segs):
        cropped_image = utils.crop_ndarray4(image.cpu().numpy(), seg.crop_region)
        cropped_image = utils.to_tensor(cropped_image)
        mask = utils.to_tensor(seg.cropped_mask)
        mask = utils.tensor_gaussian_blur_mask(mask, feather)

        if (seg.cropped_mask == 0).all().item():
            logging.info("Detailer: segment skip [empty mask]")
            continue

        cropped_mask = seg.cropped_mask if noise_mask else None

        if wildcard_chooser is not None and wmode != "LAB":
            seg_seed, wildcard_item = wildcard_chooser.get(seg)
        elif wildcard_chooser is not None and wmode == "LAB":
            seg_seed, wildcard_item = None, wildcard_chooser.get(seg)
        else:
            seg_seed, wildcard_item = None, None

        seg_seed = seed + i if seg_seed is None else seg_seed

        if not isinstance(positive, str):
            cropped_positive = [
                [condition, {
                    k: core.crop_condition_mask(v, image, seg.crop_region) if k == "mask" else v
                    for k, v in details.items()
                }]
                for condition, details in positive
            ]
        else:
            cropped_positive = positive

        if not isinstance(negative, str):
            cropped_negative = [
                [condition, {
                    k: core.crop_condition_mask(v, image, seg.crop_region) if k == "mask" else v
                    for k, v in details.items()
                }]
                for condition, details in negative
            ]
        else:
            cropped_negative = negative

        if wildcard_item and wildcard_item.strip() == '[SKIP]':
            continue
        if wildcard_item and wildcard_item.strip() == '[STOP]':
            break

        orig_cropped_image = cropped_image.clone()
        if not (isinstance(model, str) and model == "DUMMY"):
            enhanced_image, cnet_pils = enhance_detail(
                cropped_image, model, clip, vae, guide_size, guide_size_for_bbox, max_size, seg.bbox,
                seg_seed, steps, cfg, sampler_name, scheduler, cropped_positive, cropped_negative,
                cropped_mask, force_inpaint, wildcard_opt=wildcard_item,
                wildcard_opt_concat_mode=wildcard_concat_mode, detailer_hook=detailer_hook,
                refiner_ratio=refiner_ratio, refiner_model=refiner_model, refiner_clip=refiner_clip,
                refiner_positive=refiner_positive, refiner_negative=refiner_negative,
                control_net_wrapper=seg.control_net_wrapper, cycle=cycle, inpaint_model=inpaint_model,
                noise_mask_feather=noise_mask_feather, scheduler_func=scheduler_func_opt,
                vae_tiled_encode=tiled_encode, vae_tiled_decode=tiled_decode,
                start_at_step=start_at_step, end_at_step=end_at_step)
        else:
            enhanced_image, cnet_pils = cropped_image, None

        if cnet_pils is not None:
            cnet_pil_list.extend(cnet_pils)

        if enhanced_image is not None:
            image = image.cpu()
            enhanced_image = enhanced_image.cpu()
            utils.tensor_paste(image, enhanced_image, (seg.crop_region[0], seg.crop_region[1]), mask)
            enhanced_list.append(enhanced_image)
            if detailer_hook is not None:
                image = detailer_hook.post_paste(image)

            enhanced_image_alpha = utils.tensor_convert_rgba(enhanced_image)
            new_seg_image = enhanced_image.numpy()
            mask = utils.tensor_resize(mask, *utils.tensor_get_size(enhanced_image))
            utils.tensor_putalpha(enhanced_image_alpha, mask)
            enhanced_alpha_list.append(enhanced_image_alpha)
        else:
            new_seg_image = None

        cropped_list.append(orig_cropped_image)
        new_segs.append(SEG(new_seg_image, seg.cropped_mask, seg.confidence, seg.crop_region,
                            seg.bbox, seg.label, seg.control_net_wrapper))

    image_tensor = utils.tensor_convert_rgb(image)
    cropped_list.sort(key=lambda x: x.shape, reverse=True)
    enhanced_list.sort(key=lambda x: x.shape, reverse=True)
    enhanced_alpha_list.sort(key=lambda x: x.shape, reverse=True)

    return image_tensor, cropped_list, enhanced_list, enhanced_alpha_list, cnet_pil_list, (segs[0], new_segs)
