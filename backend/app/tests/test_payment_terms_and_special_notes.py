from services.parser.rule_note_extractor import (
    clean_special_notes,
    extract_rule_notes,
    extract_warranty_months,
)


def main() -> None:
    test_daol_notes()
    test_deepsigning_conditions()
    test_sysmate_led_remark()
    test_sysmate_55_remark()
    test_orion_conditions()
    test_hyosung_remark()
    test_artifact_cleanup()
    print("payment/special notes tests: ok")


def test_daol_notes() -> None:
    result = extract_rule_notes(
        """
        특기사항
        1. 상기견적은 해당건에 한함 (견적유효기간 : 견적일로부터 30일)
        2. 대금결재조건 : 협의
        3. 1차 전기 인입공사 및 통신 공사 별도
        4. 설치 구조물(보강대) / 인테리어 마감 공사 별도
        5. 제품무상보증기간 : 준공일로부터 1년
        합계 금액 (VAT 별도) ₩10,384,000
        """
    )
    assert result.payment_terms == "협의"
    assert any("전기 인입공사" in note for note in result.special_notes)
    assert not any("합계" in note or "VAT" in note for note in result.special_notes)


def test_deepsigning_conditions() -> None:
    result = extract_rule_notes(
        """
        1. 결제 조건 : 선입금 현금 결제 (발주시 100%)
        2. 납 기 : 발주 후 60일
        3. 무상 A/S : 납품일로부터 1년 무상 A/S
        4. 견적담당자 : 홍길동
        ** 영업기회 중복 확인 후 납품이 불가할 수 있습니다.
        """
    )
    assert result.payment_terms == "선입금 현금 결제 (발주시 100%)"
    assert result.delivery_terms == ["발주 후 60일"]
    assert extract_warranty_months(result.warranty_terms) == 12
    assert any("영업기회" in note for note in result.special_notes)
    assert not any("견적담당자" in note for note in result.special_notes)


def test_sysmate_led_remark() -> None:
    result = extract_rule_notes(
        """
        PAYMENT. 선입금 100%
        PACKING. Standard Packing
        VALIDITY. 45 days from today
        Remark
        1. Warranty : 1 year factory warranty
        2. Delivery : 45일 이내(발주서 접수 후)
        3. 전원 220V사용, 통신 UTP CAT.5E 사용
        4. 실내 설치 기준이며, 전기통신 공사는 제외됩니다.
        5. 현장 실사후 컨디션에 따라 비용은 변경될 수 있습니다.
        """
    )
    assert result.payment_terms == "선입금 100%"
    assert extract_warranty_months(result.warranty_terms) == 12
    assert any("전기통신 공사는 제외" in note for note in result.special_notes)
    assert any("비용은 변경" in note for note in result.special_notes)


def test_sysmate_55_remark() -> None:
    result = extract_rule_notes(
        """
        ▣ 대 금 결 재 :
        발주시100% (신규업체 선입금 조건)
        REMARK
        1. 무상유지보수 : 3년
        2. Delivery : 계약 후 60일 이내
        3. 본 견적은 전기, 통신공사 수요처 제공 기준입니다.
        4. CMS, 컨트롤러는 제외된 견적입니다.
        5. 콘텐츠 해상도, 운영관리 부분은 반드시 사전에 확인 바랍니다.
        6. 매립설치시 인테리어 마감 필수
        7. 돌출설치시 별도 기구물 제작 필수
        공급가 ₩16,280,000
        """
    )
    assert result.payment_terms == "발주시100% (신규업체 선입금 조건)"
    assert extract_warranty_months(result.warranty_terms) == 36
    assert any("CMS, 컨트롤러" in note for note in result.special_notes)
    assert not any("공급가" in note for note in result.special_notes)


def test_orion_conditions() -> None:
    result = extract_rule_notes(
        """
        Price validity : 발행 후 2주
        Payment terms : 발주 시 50%, 설치 시 50%
        납기 : 발주 후 2~3주
        설치일정 : 발주확정 후 5주 이내
        도착지 : 충북 음성(일강이앤아이)
        Warranty term : 1년 무상보증
        전기공사 별도
        본 견적서에 대하여 외부 유출 금할것을 당부드립니다.
        Bank Account : 123-456
        """
    )
    assert result.payment_terms == "발주 시 50%, 설치 시 50%"
    assert result.delivery_terms == ["발주 후 2~3주"]
    assert extract_warranty_months(result.warranty_terms) == 12
    assert result.evidence["install_location"] == "충북 음성"
    assert any("외부 유출" in note for note in result.special_notes)
    assert not any("Bank Account" in note for note in result.special_notes)


def test_hyosung_remark() -> None:
    result = extract_rule_notes(
        """
        [ Remark ]
        (1) 견적유효기간 : 견적일로부터 15일 이내
        (2) 무상보수기간 : 납품완료 후 12개월
        (3) 유상보수정비요율 : 별도협의
        (4) 도입가능일 : 별도협의
        (5) 기타사항 :
        """
    )
    assert result.quote_validity_terms == "견적일로부터 15일 이내"
    assert extract_warranty_months(result.warranty_terms) == 12
    assert result.delivery_terms == ["별도협의"]
    assert not any("기타사항" in note for note in result.special_notes)


def test_artifact_cleanup() -> None:
    notes = clean_special_notes(
        [
            "합계 금액 (VAT 별도) ₩10,384,000",
            "부가가치세 (VAT)",
            "전체 합 계 (VAT 포함)",
            "재질 : Steel / 분체도장",
            "해상도 : 1,920 x 1,080",
            "₩1,000,000 ₩9,000,000",
            "현장 실사 후 비용 변경 가능",
        ]
    )
    assert notes == ["현장 실사 후 비용 변경 가능"]


if __name__ == "__main__":
    main()
