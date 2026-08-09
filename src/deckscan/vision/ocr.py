"""Windows 내장 OCR 어댑터 + 승패 인장 판독 (설계 DES-08, ADR-002 결정 5).

P-01 프로토타입 실증: 병력 숫자는 4배 확대+이진화, 일시는 3배 확대에서 정확.
유저명·장수명 판독에는 신뢰 불가 — 라벨 "제안"에만 쓴다(ADR-002).
엔진 교체(PaddleOCR 등)는 이 모듈 교체로 한정된다.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

RESULT_DIR = Path(__file__).resolve().parents[3] / "assets" / "templates" / "result"
RESULT_BY_NAME = {"win": "승", "draw": "무", "lose": "패"}
# 실측(2026-08-09): 같은 인장 교차 소스 0.989~1.000, 다른 인장 ≤0.561
RESULT_THRESHOLD = 0.75
_BIN_THRESHOLD = 150

# 시각 구분자는 선택적 — 렌더 변형에서 콜론이 소실되면 "0134:42"처럼 붙어
# 인식된다(2026-08-09 실기 panel_fa584b). 시·분·초는 항상 2자리 렌더다.
_DATE_RE = re.compile(
    r"(\d{4})\D{0,3}(\d{1,2})\D{0,3}(\d{1,2})\D{0,4}(\d{2})\s*[:;.]?\s*(\d{2})\s*[:;.]?\s*(\d{2})")


def _upscale(crop: np.ndarray, scale: int) -> Image.Image:
    im = Image.fromarray(crop)
    return im.resize((im.width * scale, im.height * scale), Image.LANCZOS)


def _binarize(crop: np.ndarray, scale: int) -> Image.Image:
    """이진화(검은 글자/흰 배경) + 잡음 성분 제거 + 여백 패딩.

    카드 테두리 파편 같은 소형 잡음과 여백 부족이 Windows OCR의 인식 거부를
    유발한다(4.png 실측) — 성분 면적 필터와 12px 흰 여백으로 정리한다.
    """
    gray = np.asarray(_upscale(crop, scale).convert("L")).astype(np.int16)
    text = (gray >= _BIN_THRESHOLD).astype(np.uint8)   # 밝은 글자=1
    # 렌더 변형으로 획이 어두워지면 '0'이 좌우 호 2개로 끊긴다(2026-08-09 실기
    # panel_081141: OCR이 '()'로 오독) — 닫힘 연산으로 끊긴 획을 재접합한다.
    # 커널 5px는 획 틈만 잇는다(숫자 자간·'0' 중앙 구멍은 업스케일에서 그보다 넓다).
    text = cv2.morphologyEx(text, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(text, connectivity=8)
    keep = np.zeros_like(text)
    min_area = 10 * scale * scale
    for i in range(1, n):
        if stats[i][4] >= min_area:
            keep[labels == i] = 1
    out = np.where(keep == 1, 0, 255).astype(np.uint8)
    pad = 12
    out = cv2.copyMakeBorder(out, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
    return Image.fromarray(out).convert("RGB")


class OcrReader:
    def __init__(self, lang: str = "ko"):
        self.lang = lang

    def _ocr(self, img: Image.Image) -> str:
        import winocr  # 임포트 지연 — 픽스처 전용 테스트 환경 고려
        r = winocr.recognize_pil_sync(img, lang=self.lang)
        return (r.get("text", "") if isinstance(r, dict)
                else getattr(r, "text", "")) or ""

    def read_number(self, crop: np.ndarray) -> int | None:
        """병력 수 등 흰색 숫자 판독. 실패 시 None.

        숫자 자간이 넓으면 OCR이 "104 33"처럼 분리 인식한다(5.png 실측) —
        숫자 사이 공백·구두점은 접합한 뒤 최장 런을 취한다. 획이 끊긴 '0'은
        '()'로 인식된다(2026-08-09 실기) — '0'으로 되돌린다. 4배에서 인식을
        거부하는 렌더 변형이 3배에서는 정독되는 사례가 있어(panel_e1423b 실측)
        3배 이진화를 마지막 폴백으로 둔다.
        """
        for img in (_binarize(crop, 4), _upscale(crop, 4), _binarize(crop, 3)):
            text = self._ocr(img).replace("()", "0")
            text = re.sub(r"(?<=\d)[\s,.]+(?=\d)", "", text)
            runs = re.findall(r"\d+", text)
            if runs:
                return int(max(runs, key=len))
        return None

    def read_datetime(self, crop: np.ndarray) -> str | None:
        """전투 일시를 ISO 문자열로 판독. 실패 시 None."""
        for img in (_upscale(crop, 3), _binarize(crop, 3)):
            m = _DATE_RE.search(self._ocr(img))
            if m:
                y, mo, d, h, mi, s = (int(g) for g in m.groups())
                return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}"
        return None

    def suggest_label(self, crop: np.ndarray) -> str | None:
        """신규 식별자 등록용 라벨 제안 — 정확성을 보장하지 않는다(ADR-002)."""
        text = self._ocr(_upscale(crop, 4)).strip().replace("\n", " ")
        return text or None


class ResultReader:
    """승/무/패 인장 템플릿 NCC 판독. 미등록 인장은 None(증거 수확 대상)."""

    def __init__(self, template_dir: Path | str = RESULT_DIR,
                 threshold: float = RESULT_THRESHOLD):
        self.threshold = threshold
        self._templates: list[tuple[str, np.ndarray]] = []
        for path in sorted(Path(template_dir).glob("*.png")):
            stem = re.sub(r"_\d+$", "", path.stem)
            label = RESULT_BY_NAME.get(stem)
            if label:
                self._templates.append(
                    (label, np.asarray(Image.open(path).convert("RGB"))))

    def read(self, crop: np.ndarray) -> str | None:
        best_label, best = None, self.threshold
        for label, tpl in self._templates:
            if tpl.shape[0] > crop.shape[0] or tpl.shape[1] > crop.shape[1]:
                continue
            score = float(cv2.matchTemplate(crop, tpl, cv2.TM_CCOEFF_NORMED).max())
            if score > best:
                best_label, best = label, score
        return best_label
