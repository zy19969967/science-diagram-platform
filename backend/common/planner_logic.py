from __future__ import annotations

from .assets import get_asset
from .schemas import PlanRequest, PlanResponse

REMOVE_KEYWORDS = (
    "删除", "移除", "去掉", "清除", "去除", "抹掉", "擦掉", "消除", "弄掉", "删掉", "消掉",
    "erase", "remove", "delete", "clean", "clear",
)
REPLACE_KEYWORDS = (
    "替换", "换成", "改成", "变成",
    "replace", "change", "swap",
)
OUTPAINT_KEYWORDS = (
    "扩图", "扩展", "补全画布", "补边",
    "outpaint", "extend", "expand",
)
SHAPE_GUIDED_KEYWORDS = (
    "轮廓", "形状", "蒙版", "沿着选区", "贴合",
    "mask",
)


def _contains_cjk(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or (0xF900 <= cp <= 0xFAFF):
            return True
    return False


ZH_EN_DICT: dict[str, str] = {
    # Colors
    "红色": "red", "蓝色": "blue", "绿色": "green", "白色": "white", "黑色": "black",
    "黄色": "yellow", "紫色": "purple", "橙色": "orange", "粉色": "pink", "灰色": "gray",
    "棕色": "brown", "金色": "gold", "银色": "silver",
    # Common objects
    "花瓶": "flower vase", "杯子": "cup", "瓶子": "bottle", "碗": "bowl",
    "盘子": "plate", "盒子": "box", "花": "flower", "植物": "plant",
    "桌子": "table", "椅子": "chair", "手机": "phone", "电脑": "computer",
    "书本": "book", "笔": "pen", "灯": "lamp", "钟": "clock",
    "猫": "cat", "狗": "dog", "水果": "fruit", "苹果": "apple",
    "水壶": "kettle", "茶壶": "teapot", "玻璃": "glass", "球": "ball",
    "蛋糕": "cake", "面包": "bread", "石头": "stone", "木头": "wood",
    "金属": "metal", "塑料": "plastic", "陶瓷": "ceramic",
    # Adjectives
    "大": "large", "小": "small", "新": "new", "旧": "old",
    "现代": "modern", "古典": "classic", "干净": "clean",
    # Nature
    "树": "tree", "草": "grass", "天空": "sky", "云": "cloud", "水": "water",
    "山": "mountain", "河": "river", "海": "ocean", "太阳": "sun", "月亮": "moon",
    "叶子": "leaf", "森林": "forest", "土地": "ground", "火": "fire",
    # People
    "人": "person", "脸": "face", "手": "hand", "眼睛": "eye", "头发": "hair",
    # Buildings
    "房子": "house", "门": "door", "窗户": "window", "墙": "wall", "地板": "floor",
    # Vehicles
    "车": "car", "自行车": "bicycle",
    # Other
    "纸": "paper", "布": "cloth", "光": "light", "影": "shadow",
    "图案": "pattern", "纹理": "texture", "背景": "background",
}


def _translate_cjk(text: str) -> str:
    result = text
    for zh, en in sorted(ZH_EN_DICT.items(), key=lambda x: -len(x[0])):
        result = result.replace(zh, f" {en} ")
    result = " ".join(result.split())
    has_cjk = _contains_cjk(result)
    if has_cjk:
        result = " ".join(
            word for word in result.split()
            if not _contains_cjk(word) or word in ZH_EN_DICT.values()
        )
    if not result.strip():
        return "a new object"
    return result.strip()


def _inpaint_prompt(instruction: str) -> str:
    if not instruction:
        return "modify the masked region to match the surrounding scene naturally"
    if not _contains_cjk(instruction):
        return f"{instruction}. High quality, seamlessly blended with the surrounding scene."
    return "A new object placed naturally in the masked region, seamlessly blending with the surrounding scene lighting, color, and style."


def build_plan(payload: PlanRequest) -> PlanResponse:
    instruction = payload.instruction.strip()
    lowered = instruction.lower()
    selected_asset = get_asset(payload.selected_asset_id)
    warnings: list[str] = []

    is_remove = any(k in instruction or k in lowered for k in REMOVE_KEYWORDS)
    is_replace = any(k in instruction or k in lowered for k in REPLACE_KEYWORDS)
    is_outpaint = any(k in instruction or k in lowered for k in OUTPAINT_KEYWORDS)
    is_shape = bool(payload.selected_asset_id) or any(k in instruction for k in SHAPE_GUIDED_KEYWORDS)

    if is_remove:
        task = "object-removal"
    elif is_outpaint:
        task = "image-outpainting"
    elif is_shape:
        task = "shape-guided"
    else:
        task = payload.preferred_task or "text-guided"

    target_label = selected_asset.name if selected_asset else None
    recommended_asset_id = selected_asset.id if selected_asset else None

    if task == "object-removal":
        task_prompt = "Remove the masked object entirely. Fill the area with the surrounding background texture. No visible seams, ghosting, or artifacts."
        negative_prompt = "text, letters, words, watermark, dark spots, black marks, object remnants, ghost artifacts, blurry inpainting, mismatched texture, broken edges"
        reasoning = "Detected removal intent."
    elif task == "image-outpainting":
        task_prompt = "Extend the canvas outward naturally. Maintain consistent lighting, structure, and style with the original image. No visible seams."
        negative_prompt = "seam visible, mismatched style, distorted continuation, blurry extension, inconsistent lighting"
        reasoning = "Detected outpainting intent."
    elif task == "shape-guided":
        if not instruction and selected_asset:
            task_prompt = f"A clean scientific illustration of {selected_asset.prompt}, precise edges, flat vector-like style."
        elif selected_asset and selected_asset.name not in instruction:
            task_prompt = f"{_inpaint_prompt(instruction)} Keep the generated object close to {selected_asset.prompt}."
        else:
            task_prompt = _inpaint_prompt(instruction)
        negative_prompt = "deformed object, blurry label, noisy edge, duplicated object, broken outline"
        reasoning = "Detected shape or asset guidance."
    else:
        if is_replace:
            target_desc = _translate_cjk(instruction) if _contains_cjk(instruction) else instruction
            task_prompt = (
                f"{target_desc}. "
                "The object must fit naturally into the scene — matching the lighting, perspective, "
                "scale, and color tone of the surrounding image. Seamless transition, no artifacts."
            )
            reasoning = "Detected replacement intent."
        elif not instruction and selected_asset:
            task_prompt = f"Add {selected_asset.prompt} to the marked region, clean scientific illustration style."
        else:
            task_prompt = _inpaint_prompt(instruction)
            reasoning = "Default text-guided generation with mask constraint."
        negative_prompt = "blurry text, broken outline, distorted geometry, duplicated object, mismatched style"

    if not instruction:
        warnings.append("No natural language instruction provided, system will rely on task type and mask for editing.")
    if payload.selected_asset_id and not selected_asset:
        warnings.append("Selected asset not found in catalog, degraded to pure text guidance.")

    return PlanResponse(
        task=task,
        task_prompt=task_prompt,
        negative_prompt=negative_prompt,
        target_label=target_label,
        recommended_asset_id=recommended_asset_id,
        mask_strategy="user-mask",
        reasoning=reasoning,
        warnings=warnings,
    )
