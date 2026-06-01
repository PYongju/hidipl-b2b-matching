from services.ranking.schemas import PartnerProfile


SYNONYM_MAP = {
    "LED 전광판": ["LED 디스플레이", "디지털 사이니지", "전광판"],
    "비디오월": ["멀티비전", "디스플레이 월", "회의실 디스플레이"],
    "사이니지": ["디지털 사이니지", "DID"],
    "설치": ["시공", "구축", "현장 설치"],
    "커브드": ["곡면", "곡면형 LED", "커브드 디스플레이"],
    "평면": ["플랫", "평면형 LED", "플랫 디스플레이"],
}


def build_partner_embedding_text(partner_profile: PartnerProfile) -> str:
    specialty_tags = [tag for tag in partner_profile.specialty_tags if tag]
    solution_keywords = []

    for tag in specialty_tags:
        solution_keywords.append(tag)
        solution_keywords.extend(SYNONYM_MAP.get(tag, []))

    deduped_keywords = []
    for keyword in solution_keywords:
        if keyword not in deduped_keywords:
            deduped_keywords.append(keyword)

    partner_type = "프리미엄 파트너" if partner_profile.is_premium else "일반 파트너"

    return "\n".join(
        [
            f"파트너명: {partner_profile.name}",
            f"전문 분야: {', '.join(specialty_tags)}",
            f"솔루션 키워드: {', '.join(deduped_keywords)}",
            f"파트너 유형: {partner_type}",
        ]
    )
