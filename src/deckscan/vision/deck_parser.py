"""펼친 덱 패널 → BattleRecord (설계 DES-05 v2, DCR-001).

ui_telegram의 패널 상수를 앵커 y로 평행이동해 필드를 크롭하고(가정 A-07),
필드별 실패를 모아 ok|partial|failed를 판정한다(NFR-01). 실패 필드 크롭은
증거로 저장한다(NFR-03) — 미수확 인장·미확보 글리프의 수확 원본이 된다.

좌우 역할: 패널 좌측은 항상 아군이지만 공격/수비 여부는 전보마다 다르다
(아군=수비 전보는 반전 — 2026-08-09 실기 실증). 좌측 세로 라벨('공격'/'수비')
템플릿 비교로 판정한다(DCR-001).
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import numpy as np
from PIL import Image

import cv2

from ..nav import ui_telegram as ui
from ..nav.list_walker import ui_template
from ..store.datastore import (BattleRecord, DataStore, SlotRecord,
                               make_battle_key, make_fallback_key)
from .digits import DigitReader
from .identity import IdentityMatcher
from .ocr import OcrReader, ResultReader

log = logging.getLogger(__name__)

_LEVEL_RE = re.compile(r"\d{1,2}")


def _crop(frame: np.ndarray, box: tuple[int, int, int, int], dy: int) -> np.ndarray:
    x0, y0, x1, y1 = box
    return frame[y0 + dy:y1 + dy, x0:x1]


class DeckParser:
    def __init__(self, store: DataStore, root: Path,
                 evidence_dir: Path | str | None = None):
        root = Path(root)
        self.users = IdentityMatcher(store, root, "user",
                                     threshold=ui.USER_NCC_THRESHOLD)
        self.generals = IdentityMatcher(store, root, "general")
        self.alliances = IdentityMatcher(store, root, "alliance",
                                         threshold=ui.ALLI_NCC_THRESHOLD)
        self.digits = DigitReader()
        self.ocr = OcrReader()
        self.results = ResultReader()
        self.evidence_dir = Path(evidence_dir) if evidence_dir is not None \
            else root / "output" / "evidence"

    def parse(self, frame: np.ndarray,
              anchor_y: int = ui.PANEL_ANCHOR_Y) -> BattleRecord:
        """클라이언트 프레임과 패널 앵커 y(행 헤더 top)로 전보 1건을 파싱한다."""
        dy = anchor_y - ui.PANEL_ANCHOR_Y
        panel = _crop(frame, ui.PANEL_REGION, dy)
        pid = hashlib.sha1(panel.tobytes()).hexdigest()[:12]
        failed: list[str] = []

        def fail(field: str, crop: np.ndarray) -> None:
            failed.append(field)
            self._save_evidence(pid, field, crop)

        def ident(matcher: IdentityMatcher, crop: np.ndarray, field: str,
                  label_crop: np.ndarray | None = None
                  ) -> tuple[int | None, float | None]:
            label = self._try(self._suggest,
                              crop if label_crop is None else label_crop)
            got = self._try(matcher.resolve, crop, label)
            if got is None:
                fail(field, crop)
                return None, None
            return got[0], got[1]

        left_attacks = self._left_attacks(frame, dy)
        if left_attacks is None:
            fail("side_label", _crop(frame, ui.SIDE_LABEL_BOX, dy))
            left_attacks = True   # 판정 불능 시 다수 사례 기본값 — partial로 표면화

        left_user, _ = ident(self.users, _crop(frame, ui.USER_ATT, dy),
                             "attacker" if left_attacks else "defender")
        right_user, _ = ident(self.users, _crop(frame, ui.USER_DEF, dy),
                              "defender" if left_attacks else "attacker")
        left_alli, _ = ident(self.alliances, _crop(frame, ui.ALLI_ATT, dy),
                             "attacker_alliance" if left_attacks
                             else "defender_alliance")
        right_alli, _ = ident(self.alliances, _crop(frame, ui.ALLI_DEF, dy),
                              "defender_alliance" if left_attacks
                              else "attacker_alliance")
        if left_attacks:
            attacker_id, defender_id = left_user, right_user
            att_alli, def_alli = left_alli, right_alli
        else:
            attacker_id, defender_id = right_user, left_user
            att_alli, def_alli = right_alli, left_alli

        date_crop = _crop(frame, ui.DATE_BOX, dy)
        battle_time = self._try(self.ocr.read_datetime, date_crop)
        if battle_time is None:
            fail("battle_time", date_crop)
        seal_crop = _crop(frame, ui.SEAL_BOX, dy)
        result = self._try(self.results.read, seal_crop)
        if result is None:
            fail("result", seal_crop)

        left_side, right_side = ("attack", "defend") if left_attacks \
            else ("defend", "attack")
        slots: list[SlotRecord] = []
        for i in range(6):
            side, slot_no = (left_side, i + 1) if i < 3 else (right_side, i - 2)
            tag = f"{side}{slot_no}"
            name_crop = _crop(frame, ui.NAME_BAR_BOXES[i], dy)
            troops_crop = _crop(frame, ui.TROOPS_BOXES[i], dy)
            level_txt = self._read_level(name_crop)
            troops = self._try(self.ocr.read_number, troops_crop)
            if level_txt == "" and troops is None:
                continue                       # 빈 카드 칸(A-03) — 실패가 아니다
            gid, score = ident(self.generals,
                               _crop(frame, ui.PORTRAIT_BOXES[i], dy),
                               f"{tag}_general", label_crop=name_crop)
            level = int(level_txt) if level_txt and \
                _LEVEL_RE.fullmatch(level_txt) else None
            if level is None:
                fail(f"{tag}_level", name_crop)
            if troops is None:
                fail(f"{tag}_troops", troops_crop)
            if gid is None and level is None and troops is None:
                continue                       # 정보가 전혀 없는 슬롯은 남기지 않는다
            slots.append(SlotRecord(side, slot_no, gid, level, troops, score))

        if battle_time is None and attacker_id is None \
                and defender_id is None and not slots:
            key, status = make_fallback_key(panel.tobytes()), "failed"
        else:
            key = make_battle_key(battle_time, attacker_id, defender_id, slots)
            status = "partial" if failed else "ok"
        if failed:
            log.warning("파싱 %s: 실패 필드 %s", pid, ", ".join(failed))
        return BattleRecord(key, battle_time, result, attacker_id, defender_id,
                            att_alli, def_alli, None, status, slots)

    # -- 내부 유틸 -----------------------------------------------------------

    def _left_attacks(self, frame: np.ndarray, dy: int) -> bool | None:
        """좌측 세로 라벨('공격'/'수비') 비교 판정. 판정 불능이면 None."""
        try:
            crop = _crop(frame, ui.SIDE_LABEL_BOX, dy)
            scores = {}
            for key, name in (("attack", "side_attack.png"),
                              ("defend", "side_defend.png")):
                tpl = ui_template(name)[3:-3, 3:-3]
                scores[key] = float(cv2.matchTemplate(
                    crop, tpl, cv2.TM_CCOEFF_NORMED).max())
            best = max(scores, key=scores.get)
            if scores[best] < ui.SIDE_MIN_SCORE:
                return None
            return best == "attack"
        except Exception:
            log.exception("측면 라벨 판정 예외")
            return None

    def _read_level(self, name_crop: np.ndarray) -> str | None:
        """이름 바에서 레벨 문자열을 읽는다. ""=텍스트 없음, None=예외."""
        try:
            txt = self.digits.read(name_crop)
            if txt and not _LEVEL_RE.fullmatch(txt):
                repaired = self.digits.read(name_crop, repair=True)
                if _LEVEL_RE.fullmatch(repaired):
                    return repaired
            return txt
        except Exception:
            log.exception("레벨 판독 예외")
            return None

    def _suggest(self, crop: np.ndarray) -> str | None:
        """등록 제안 라벨 — 이름 바의 선행 레벨 숫자("50 가후")는 제거한다."""
        text = self.ocr.suggest_label(crop)
        return re.sub(r"^\s*\d+\s+", "", text) if text else None

    def _try(self, fn, *args):
        try:
            return fn(*args)
        except Exception:
            log.exception("판독 예외: %s", getattr(fn, "__name__", fn))
            return None

    def _save_evidence(self, pid: str, field: str, crop: np.ndarray) -> None:
        try:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            Image.fromarray(np.ascontiguousarray(crop)).save(
                self.evidence_dir / f"{pid}_{field}.png")
        except Exception:
            log.exception("증거 저장 실패: %s_%s", pid, field)
