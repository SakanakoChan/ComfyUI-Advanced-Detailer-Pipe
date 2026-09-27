# ComfyUI Advanced Detailer Pipe

<img width="551" height="959" alt="image" src="https://github.com/user-attachments/assets/8254b036-04f4-4b27-8b13-1454ea00b728" />


## 中文

为 ComfyUI-Impact-Pack 的 **DetailerDebug (SEGS/pipe)** 增加 Advanced KSampler 风格的起始步数和终止步数控制。

新节点名称：**DetailerDebug (SEGS/pipe Advanced)**

## 功能

- 保留原节点的 SEGS、`BASIC_PIPE` 输入和调试输出。
- 使用 `steps` 指定总采样步数，并用 `start_at_step` 和 `end_at_step` 选择采样范围。
- 采样结束时执行完整去噪；节点不再提供原 Detailer 的 `denoise` 控件。

`end_at_step` 默认值为 `10000`，实际采样会在总步数范围内结束。例如 `steps=20`、`start_at_step=12`、`end_at_step=10000` 表示从第 12 步采样到第 20 步。

## 从原 Detailer 设置换算

原 Detailer 根据 `steps` 和 `denoise` 计算采样范围：

```text
total_steps = floor(steps / denoise)
start_at_step = total_steps - steps
end_at_step = total_steps
```

| 原 Detailer 设置 | 新节点 `steps` | `start_at_step` | `end_at_step` |
| --- | ---: | ---: | ---: |
| 4 步，denoise 0.4 | 10 | 6 | 10 |
| 8 步，denoise 0.4 | 20 | 12 | 20 |

## 输出

节点保留原 Debug Pipe 的输出：`image`、`segs`、`basic_pipe`、`cropped`、`cropped_refined`、`cropped_refined_alpha` 和 `cnet_images`。

## 安装

1. 将本插件放到 `ComfyUI/custom_nodes/ComfyUI-Advanced-Detailer-Pipe`。
2. 安装 ComfyUI-Impact-Pack，并确保它与本插件位于同一个 `custom_nodes` 目录。
3. 重启 ComfyUI。

### Impact Pack 版本要求

本插件需要 Impact Pack 的 detailer 采样接口支持 `start_at_step` 和 `end_at_step` 参数。原版 Impact Pack 如果没有包含这项接口改动，运行新节点时会因不认识这两个参数而报错；请使用包含对应改动的 Impact Pack 版本。

## English

Adds Advanced KSampler-style start and end step controls to ComfyUI-Impact-Pack's **DetailerDebug (SEGS/pipe)** node.

Node name: **DetailerDebug (SEGS/pipe Advanced)**

### Features

- Keeps the original node's SEGS and `BASIC_PIPE` inputs and debug outputs.
- Uses `steps` for the total sampling steps, with `start_at_step` and `end_at_step` selecting the sampling range.
- Fully denoises at the end of sampling. The original Detailer's `denoise` input is omitted.

The default `end_at_step` is `10000`; sampling ends at the total step count. For example, `steps=20`, `start_at_step=12`, and `end_at_step=10000` samples from step 12 through step 20.

### Converting settings from the original Detailer

The original Detailer calculates its sampling range from `steps` and `denoise`:

```text
total_steps = floor(steps / denoise)
start_at_step = total_steps - steps
end_at_step = total_steps
```

| Original Detailer setting | New node `steps` | `start_at_step` | `end_at_step` |
| --- | ---: | ---: | ---: |
| 4 steps, denoise 0.4 | 10 | 6 | 10 |
| 8 steps, denoise 0.4 | 20 | 12 | 20 |

### Outputs

Keeps the original Debug Pipe outputs: `image`, `segs`, `basic_pipe`, `cropped`, `cropped_refined`, `cropped_refined_alpha`, and `cnet_images`.

### Installation

1. Place this plugin in `ComfyUI/custom_nodes/ComfyUI-Advanced-Detailer-Pipe`.
2. Install ComfyUI-Impact-Pack alongside this plugin in the same `custom_nodes` directory.
3. Restart ComfyUI.

#### Impact Pack version requirement

This plugin requires the Impact Pack detailer sampling interface to support the `start_at_step` and `end_at_step` parameters. If your Impact Pack version does not include this interface change, the node will report an unexpected keyword argument error. Use an Impact Pack version that includes the corresponding changes.
