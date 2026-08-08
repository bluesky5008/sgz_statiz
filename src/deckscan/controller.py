"""실행 요약·라벨 확정 절차 (설계 DES-10, FR-06·FR-07).

scan 오케스트레이션(내비게이션·목록 순회·예외 경계)은 TASK-09·10의 실기
부분이 갖춰진 뒤 이 모듈에 추가한다.
"""

from __future__ import annotations

import logging
from typing import Callable

from .store.datastore import DataStore

log = logging.getLogger(__name__)


def label_pending(store: DataStore, ask: Callable[[str], str],
                  opener: Callable[[str], None] | None = None) -> int:
    """pending 식별자를 순회하며 라벨을 확정한다(FR-07, AC-06).

    ask(프롬프트)의 입력 규약: 빈값=건너뜀(pending 유지), 'q'=중단,
    그 외=라벨 확정. opener(템플릿 경로)는 크롭 표시용(CLI가 뷰어 주입).
    반환: 확정한 식별자 수.
    """
    done = 0
    for row in store.pending_identities():
        templates = store.templates_of(row["identity_id"])
        template = templates[0] if templates else "?"
        if opener is not None:
            try:
                opener(template)
            except Exception:
                log.warning("크롭 표시 실패: %s", template)
        answer = ask(
            f"[{row['namespace']}#{row['identity_id']}] "
            f"제안='{row['label'] or ''}' 크롭={template} "
            f"→ 라벨 입력(빈값=건너뜀, q=종료): ").strip()
        if answer == "q":
            break
        if not answer:
            continue
        store.confirm_label(row["identity_id"], answer)
        done += 1
    return done


def summarize_run(store: DataStore, run_id: int) -> str:
    """run 요약 문자열(FR-06) — 처리·저장·실패 건수와 pending 안내."""
    run = store.get_run(run_id)
    lines = [f"run #{run_id} {run['status']} — 처리 {run['processed'] or 0}건, "
             f"저장 {run['saved'] or 0}건, 실패 {run['failed'] or 0}건"]
    pending = len(store.pending_identities())
    if pending:
        lines.append(f"미확정 식별자 pending {pending}건 — "
                     f"`deckscan label`로 라벨을 확정하세요")
    return "\n".join(lines)
