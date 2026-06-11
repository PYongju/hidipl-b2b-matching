from services.ranking.schemas import PartnerProfile


SOLUTION_SYNONYMS = {
    "led": ["LED전광판", "LED 전광판", "LED display", "LED 디스플레이", "전광판", "indoor LED", "outdoor LED", "회의실 디스플레이"],
    "video_wall": ["비디오월", "video wall", "multi vision", "멀티비전", "멀티비젼", "LCD wall", "meeting room display"],
    "signage": ["사이니지", "디지털사이니지", "디지털 사이니지", "digital signage", "DID", "display system"],
    "transparent": ["투명디스플레이", "투명 OLED", "투명LED", "transparent display"],
    "kiosk": ["키오스크", "KIOSK", "self service kiosk"],
    "installation": ["설치", "시공", "현장 설치", "installation", "construction", "site installation"],
    "curved": ["커브드 LED", "커브드 디스플레이", "curved LED", "curved display"],
    "flat": ["평면 LED", "평면 디스플레이", "flat LED", "flat display"],
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
        f"파트너명: {partner_profile.name}",
        f"전문 분야: {', '.join(specialty_tags)}",
        f"솔루션 키워드: {', '.join(keywords)}",
        f"partner_type: {partner_type}",
    ]
    if partner_profile.installation_count is not None:
        lines.append(f"설치 실적 수: {partner_profile.installation_count}")

    solution_history = _format_count_map(partner_profile.solution_breakdown)
    industry_history = _format_count_map(partner_profile.industry_breakdown)
    scale_history = _format_count_map(partner_profile.scale_breakdown)
    if solution_history:
        lines.append(f"솔루션 이력: {solution_history}")
    if industry_history:
        lines.append(f"산업군 이력: {industry_history}")
    if scale_history:
        lines.append(f"규모 이력: {scale_history}")
    return "\n".join(lines)


def _synonyms_for_tags(tags: list[str]) -> list[str]:
    synonyms: list[str] = []
    for tag in tags:
        normalized = tag.lower().replace(" ", "")
        if "led" in normalized or "전광판" in tag:
            synonyms.extend(SOLUTION_SYNONYMS["led"])
        if "비디오월" in tag or "video" in normalized or "wall" in normalized or "멀티비" in tag:
            synonyms.extend(SOLUTION_SYNONYMS["video_wall"])
        if "사이니지" in tag or "signage" in normalized or "did" in normalized:
            synonyms.extend(SOLUTION_SYNONYMS["signage"])
        if "투명" in tag or "transparent" in normalized:
            synonyms.extend(SOLUTION_SYNONYMS["transparent"])
        if "키오스크" in tag or "kiosk" in normalized:
            synonyms.extend(SOLUTION_SYNONYMS["kiosk"])
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
    return ", ".join(f"{key} {count}건" for key, count in items if key)


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
