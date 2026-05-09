# Qwen-Image Prompt Policy

## Current Objective

Qwen-Image-Edit is the default local masked-edit provider. PowerPaint remains a separate legacy/manual provider. Qwen prompts must be short Chinese edit instructions that preserve the user's original meaning. Automatic prompt enhancement is disabled by default; users write the prompt they want.

## Locked Prompt Rules

- Qwen uses the original image plus the user's normalized mask.
- Qwen prompt text is Chinese.
- Keep the user's original action and target: delete, replace, repaint, adjust, or transform are not split into separate hard-coded templates.
- Do not reuse PowerPaint prompt wording.
- Do not introduce single-object or multi-target concepts.
- Do not add long negative constraints.
- Do not add unrequested objects, counts, layout, or scene plans.
- Qwen negative prompt defaults to a single space (`" "`).
- Qwen3.5 prompt enhancement is off unless `QWEN_IMAGE_PROMPT_ENHANCER_ENABLED=true`.

## Unified Template

```text
只修改 mask 内区域。{short Chinese user-intent instruction}。{short style sentence}
```

Scientific diagrams:

```text
保持科学线稿风格，白底、轮廓清晰。
```

Photographic images:

```text
保持照片风格，光照、透视和材质与原图一致。
```

## Examples

User:

```text
把烧杯变成锥形瓶
```

Qwen prompt:

```text
只修改 mask 内区域。把烧杯变成锥形瓶（窄颈、宽底）。未选区保持原图不变。保持科学线稿风格，白底、轮廓清晰。
```

User:

```text
删除选区里的杯子
```

Qwen prompt:

```text
只修改 mask 内区域。删除选区里的杯子。未选区保持原图不变。保持照片风格，光照、透视和材质与原图一致。
```

## Qwen3.5 Enhancer Scope

The local Qwen3.5 planner enhancer is optional and disabled by default because the 4B model can reverse edit semantics. When explicitly enabled, it rewrites only the Qwen edit instruction. It must output Chinese, preserve the original intent, stay direct and specific, and avoid long constraints. If it returns English, reverses the user's Chinese edit action, or introduces known-wrong lab geometry such as a wide-mouth narrow-base conical flask, the gateway falls back to the deterministic Chinese prompt.
