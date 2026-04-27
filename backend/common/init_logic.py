from __future__ import annotations

import random
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .schemas import (
    InitCandidate,
    InitGenerateRequest,
    InitGenerateResponse,
    ScenePlanObject,
    ScenePlanRelation,
    ScenePlanRequest,
    ScenePlanResponse,
)
from .utils.images import encode_image_to_data_url

PROVIDER = "deterministic-fallback"
DEFAULT_NEGATIVE_PROMPT = "photorealistic, watermark, blurry text, messy labels, extra arrows"


@dataclass(frozen=True)
class _Concept:
    keyword: str
    label: str
    english: str
    role: str
    visual: str


CONCEPTS = (
    _Concept("底物", "底物", "substrate", "input", "small molecule cluster"),
    _Concept("substrate", "底物", "substrate", "input", "small molecule cluster"),
    _Concept("酶", "酶", "enzyme", "process", "rounded protein shape"),
    _Concept("enzyme", "酶", "enzyme", "process", "rounded protein shape"),
    _Concept("产物", "产物", "product", "output", "separated molecule cluster"),
    _Concept("product", "产物", "product", "output", "separated molecule cluster"),
    _Concept("烧杯", "烧杯", "beaker", "container", "laboratory beaker"),
    _Concept("beaker", "烧杯", "beaker", "container", "laboratory beaker"),
    _Concept("试管", "试管", "test tube", "container", "test tube"),
    _Concept("test tube", "试管", "test tube", "container", "test tube"),
    _Concept("细胞", "细胞", "cell", "structure", "cell outline"),
    _Concept("cell", "细胞", "cell", "structure", "cell outline"),
    _Concept("dna", "DNA", "DNA", "structure", "double helix marker"),
    _Concept("箭头", "箭头", "arrow", "relation", "direction arrow"),
    _Concept("arrow", "箭头", "arrow", "relation", "direction arrow"),
)


def _contains(instruction: str, keyword: str) -> bool:
    return keyword.lower() in instruction.lower()


def _extract_concepts(instruction: str) -> list[_Concept]:
    seen: set[str] = set()
    matches: list[_Concept] = []
    for concept in CONCEPTS:
        if concept.label in seen:
            continue
        if _contains(instruction, concept.keyword):
            matches.append(concept)
            seen.add(concept.label)

    if not matches:
        matches = [
            _Concept("input", "输入", "input signal", "input", "labeled input node"),
            _Concept("process", "过程", "scientific process", "process", "central process node"),
            _Concept("output", "输出", "output result", "output", "labeled output node"),
        ]

    return [concept for concept in matches if concept.role != "relation"][:5]


def _diagram_type(instruction: str) -> str:
    lowered = instruction.lower()
    if "酶" in instruction or "enzyme" in lowered:
        return "enzyme_reaction_diagram"
    if "细胞" in instruction or "cell" in lowered:
        return "cell_structure_diagram"
    if "实验" in instruction or "烧杯" in instruction or "试管" in instruction or "chem" in lowered:
        return "laboratory_process_diagram"
    return "scientific_process_diagram"


def _position_for(index: int, total: int) -> str:
    if total == 1:
        return "center"
    if index == 0:
        return "left"
    if index == total - 1:
        return "right"
    return "center"


def build_scene_plan(payload: ScenePlanRequest) -> ScenePlanResponse:
    instruction = payload.instruction.strip() or "create a clean scientific process diagram"
    concepts = _extract_concepts(instruction)
    objects: list[ScenePlanObject] = []
    for index, concept in enumerate(concepts):
        objects.append(
            ScenePlanObject(
                id=f"obj_{index + 1}",
                name=concept.label,
                role=concept.role,
                position=_position_for(index, len(concepts)),
                visual=concept.visual,
            )
        )

    relations = [
        ScenePlanRelation(source=objects[index].id, target=objects[index + 1].id)
        for index in range(max(0, len(objects) - 1))
    ]
    labels = [item.name for item in objects]
    english_objects = ", ".join(concept.english for concept in concepts)
    positive_prompt = (
        f"clean scientific diagram, {payload.style}, white background, "
        f"objects: {english_objects}, connected by arrows"
    )
    warnings = [
        "当前初图由确定性 fallback 渲染器生成；后续阶段将替换为 FLUX 候选初图服务。"
    ]

    return ScenePlanResponse(
        diagram_type=_diagram_type(instruction),
        width=payload.width,
        height=payload.height,
        instruction=instruction,
        objects=objects,
        relations=relations,
        labels=labels,
        style=payload.style,
        positive_prompt=positive_prompt,
        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
        render_text_as_vector=False,
        candidate_count=payload.candidate_count,
        seed=payload.seed,
        provider=PROVIDER,
        warnings=warnings,
    )


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int]) -> None:
    draw.line((start, end), fill=color, width=5)
    x1, y1 = start
    x2, y2 = end
    direction = 1 if x2 >= x1 else -1
    head = [(x2, y2), (x2 - direction * 18, y2 - 10), (x2 - direction * 18, y2 + 10)]
    draw.polygon(head, fill=color)


def _render_candidate(plan: ScenePlanResponse, seed: int, index: int) -> Image.Image:
    rng = random.Random(seed + index * 9973)
    width, height = plan.width, plan.height
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = _font(max(18, width // 38))
    label_font = _font(max(16, width // 54))
    small_font = _font(max(12, width // 72))

    palette = [
        ("#dbeafe", "#1d4ed8"),
        ("#dcfce7", "#15803d"),
        ("#fef3c7", "#b45309"),
        ("#fce7f3", "#be185d"),
        ("#ede9fe", "#6d28d9"),
    ]
    accent = ("#334155", "#475569", "#0f766e")[index % 3]
    margin = max(44, width // 18)
    top = max(96, height // 5)
    usable_w = width - margin * 2
    object_count = max(1, len(plan.objects))
    gap = usable_w // max(1, object_count - 1) if object_count > 1 else 0
    centers: list[tuple[int, int]] = []

    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=24, outline="#cbd5e1", width=3, fill="#ffffff")
    draw.text((margin, 42), plan.diagram_type.replace("_", " ").title(), fill="#0f172a", font=title_font)
    draw.text((margin, 78), f"provider: {PROVIDER} | seed: {seed}", fill="#64748b", font=small_font)

    for item_index, item in enumerate(plan.objects):
        cx = width // 2 if object_count == 1 else margin + item_index * gap
        cy = top + rng.randint(-20, 20)
        centers.append((cx, cy))
        fill, stroke = palette[item_index % len(palette)]
        box_w = max(140, width // 7)
        box_h = max(88, height // 8)
        box = (cx - box_w // 2, cy - box_h // 2, cx + box_w // 2, cy + box_h // 2)
        draw.rounded_rectangle(box, radius=24, fill=fill, outline=stroke, width=4)
        draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=stroke)
        label = item.name if item.name.isascii() else item.id.replace("_", " ").title()
        draw.text((box[0] + 18, box[3] + 12), label, fill="#0f172a", font=label_font)
        draw.text((box[0] + 18, box[3] + 40), item.visual[:34], fill="#475569", font=small_font)

    for relation_index in range(max(0, len(centers) - 1)):
        start = (centers[relation_index][0] + max(74, width // 14), centers[relation_index][1])
        end = (centers[relation_index + 1][0] - max(74, width // 14), centers[relation_index + 1][1])
        _draw_arrow(draw, start, end, accent)

    footer = "Initial canvas fallback. Select this candidate, then refine it with Qwen / SAM-2 / PowerPaint."
    draw.text((margin, height - 76), footer, fill="#64748b", font=small_font)
    return image


def build_init_candidates(payload: InitGenerateRequest) -> InitGenerateResponse:
    plan = payload.scene_plan
    base_seed = plan.seed if payload.seed is None else payload.seed
    candidates: list[InitCandidate] = []
    for index in range(plan.candidate_count):
        candidate_seed = base_seed + index
        image = _render_candidate(plan, candidate_seed, index)
        candidates.append(
            InitCandidate(
                id=f"init_{index + 1}",
                image=encode_image_to_data_url(image),
                seed=candidate_seed,
                provider=PROVIDER,
                score=round(0.72 + index * 0.04, 2),
                width=plan.width,
                height=plan.height,
                metadata={
                    "diagram_type": plan.diagram_type,
                    "labels": plan.labels,
                    "render_text_as_vector": plan.render_text_as_vector,
                    "vector_text_layer": False,
                },
            )
        )

    return InitGenerateResponse(provider=PROVIDER, scene_plan=plan, candidates=candidates)
