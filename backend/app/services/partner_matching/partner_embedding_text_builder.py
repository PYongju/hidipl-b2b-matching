from services.ranking.schemas import PartnerProfile


SOLUTION_SYNONYMS = {
    "led": ["LED display", "digital signage", "indoor LED", "outdoor LED"],
    "video_wall": ["video wall", "multi vision", "LCD wall", "meeting room display"],
    "signage": ["digital signage", "DID", "display system"],
    "installation": ["installation", "construction", "site installation"],
    "curved": ["curved LED", "curved display"],
    "flat": ["flat LED", "flat display"],
}


def build_partner_embedding_text(partner_profile: PartnerProfile) -> str:
    specialty_tags = [tag for tag in partner_profile.specialty_tags if tag]
    keywords = _dedupe(
        [
            *specialty_tags,
            *_synonyms_for_tags(specialty_tags),
            *list((partner_profile.solution_breakdown or {}).keys()),
            *list((partner_profile.industry_breakdown or {}).keys()),
            *list((partner_profile.scale_breakdown or {}).keys()),
        ]
    )

    partner_type = "premium partner" if partner_profile.is_premium else "standard partner"
    lines = [
        f"partner_name: {partner_profile.name}",
        f"specialty_tags: {', '.join(specialty_tags)}",
        f"solution_keywords: {', '.join(keywords)}",
        f"partner_type: {partner_type}",
    ]
    if partner_profile.installation_count is not None:
        lines.append(f"installation_count: {partner_profile.installation_count}")

    solution_history = _format_count_map(partner_profile.solution_breakdown)
    industry_history = _format_count_map(partner_profile.industry_breakdown)
    scale_history = _format_count_map(partner_profile.scale_breakdown)
    if solution_history:
        lines.append(f"solution_history: {solution_history}")
    if industry_history:
        lines.append(f"industry_history: {industry_history}")
    if scale_history:
        lines.append(f"scale_history: {scale_history}")
    return "\n".join(lines)


def _synonyms_for_tags(tags: list[str]) -> list[str]:
    synonyms: list[str] = []
    for tag in tags:
        normalized = tag.lower().replace(" ", "")
        if "led" in normalized or "전광" in tag:
            synonyms.extend(SOLUTION_SYNONYMS["led"])
        if "비디오" in tag or "video" in normalized or "wall" in normalized:
            synonyms.extend(SOLUTION_SYNONYMS["video_wall"])
        if "사이니지" in tag or "signage" in normalized or "did" in normalized:
            synonyms.extend(SOLUTION_SYNONYMS["signage"])
        if "설치" in tag or "시공" in tag or "install" in normalized:
            synonyms.extend(SOLUTION_SYNONYMS["installation"])
        if "커브" in tag or "curved" in normalized:
            synonyms.extend(SOLUTION_SYNONYMS["curved"])
        if "평면" in tag or "flat" in normalized:
            synonyms.extend(SOLUTION_SYNONYMS["flat"])
    return synonyms


def _format_count_map(values: dict[str, int] | None, *, limit: int = 6) -> str:
    if not values:
        return ""
    items = sorted(values.items(), key=lambda item: item[1], reverse=True)[:limit]
    return ", ".join(f"{key} {count}" for key, count in items if key)


def _dedupe(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped
