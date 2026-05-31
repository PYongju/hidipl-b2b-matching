# 새 카테고리·키 추가는 이 파일에서만 관리한다.

SPEC_KEYS = {
    "DISPLAY_LED": {
        "pitch_mm": float,
        "cabinet_size_mm": str,
        "brightness_nit": int,
        "full_screen_size_mm": str,
    },
    "DISPLAY_LCD": {
        "panel_size_inch": float,
        "bezel_mm": float,
        "brightness_nit": int,
        "resolution": str,
        "panel_size_mm": str,
    },
    "PLAYER": {
        "model": str,
        "spec": str,
    },
    "INSTALL": {
        "scope": str,
    },
}
