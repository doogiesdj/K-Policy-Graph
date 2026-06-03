"""
Project HARMONIA (NASIS)
다부처 갈등 조정 — 심리적 수정 내시 바게닝(Nash Bargaining) 범용 엔진

행동게임이론의 심리적 편향 7종을 정량화하여 내시 바게닝 목적함수에 반영하고,
두 행위자(부처·기관·이해관계자)의 심리적 저항을 최소화하는 최적 배분(x_A*, x_B*)을 도출한다.

적용 가능한 갈등 유형:
  - 예산·재원 배분      (총 예산 100 → A부처 54, B부처 46)
  - 사업 영역·관할권    (사업 지분 0~100점 척도)
  - 인력·조직 배분      (정원 총수 기준)
  - 규제·정책 우선순위  (정책 비중 점수)
  - 기타 단일 축 협상   (자원을 0~100 정규화하여 입력)

반영된 심리 편향 7종:
  1. 자기고양 편향       bias_alpha  (α)
  2. 부존 효과·매몰비용  bias_lambda (λ)
  3. 고정된 파이 편향    bias_gamma  (γ)  ← 신규
  4. 앵커링 효과         bias_delta  (δ)  ← 신규
  5. 후회 회피           bias_rho    (ρ)  ← 신규
  6. 반응적 가치하락     hostility_AB (H)
  7. 평판 위험·청중 효과 min_reputation_M (M)

Tech Stack: Python 3.10+ / FastAPI / Pydantic / SciPy

실행:
    pip install fastapi uvicorn scipy pydantic numpy
    python -m uvicorn main:app --reload
    # http://127.0.0.1:8000/docs 에서 /api/v1/coordination/solve 테스트

단독 실행(서버 없이 데모):
    python main.py
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from scipy.optimize import minimize_scalar

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
# 체면 마지노선(M_i) 위반 시 부과할 "무한대(∞)" 대용 페널티 상수
REPUTATION_INF_PENALTY = 1e9

# 결렬점(d_i) 대비 잉여(surplus)가 0 이하가 되는 것을 막기 위한 수치 안정용 하한
SURPLUS_FLOOR = 1e-6


# ---------------------------------------------------------------------------
# Pydantic 데이터 모델 (온톨로지 Actor / Psychological Profile 매핑)
# ---------------------------------------------------------------------------
class Actor(BaseModel):
    """행위자 레이어 + 심리 프로파일 레이어를 하나로 묶은 입력 모델.

    부처·기관·이해관계자 등 협상 당사자 한 쪽을 표현한다.
    """

    name: str = Field(..., description="행위자 명칭 (부처명, 기관명 등)")
    weight_w: float = Field(..., gt=0, description="협상 권한 가중치 w_i (AHP 점수 등)")
    disagreement_d: float = Field(..., description="결렬점 d_i (협상 결렬 시 손실 수치)")
    historical_x0: float = Field(..., description="준거점 x_0 (전년도 배분·기존 점유율 등 기준값)")

    # --- 심리 편향 7종 ---
    # 1. 자기고양 편향 (Self-Serving Bias)
    bias_alpha: float = Field(1.1, ge=1.0, description="[편향①] 자기고양 편향 α_i: 자기 몫을 과대 인식 (≥1, 기본 1.1)")

    # 2. 부존 효과·매몰비용 오류 (Endowment Effect & Sunk Cost)
    bias_lambda: float = Field(2.2, ge=0, description="[편향②] 손실 회피·부존 효과 λ_i: 준거점 이하 손실 민감도 (기본 2.2)")

    # 3. 고정된 파이 편향 (Fixed-Pie Bias)
    bias_gamma: float = Field(0.3, ge=0, description="[편향③] 고정된 파이 편향 γ_i: 상대 몫을 내 손실로 인식하는 제로섬 사고 (기본 0.3)")

    # 4. 앵커링 효과 (Anchoring & Adjustment)
    bias_delta: float = Field(0.5, ge=0, description="[편향④] 앵커링 민감도 δ_i: 첫 요구안 기준점에서 내려오는 저항 강도 (기본 0.5)")
    anchor_demand: Optional[float] = Field(None, ge=0, description="[편향④] 앵커 기준값 a_i: 협상 첫 요구안 (미입력 시 historical_x0 × 1.5 자동 적용)")

    # 5. 후회 회피·승자의 저주 (Regret Aversion & Winner's Curse)
    bias_rho: float = Field(0.3, ge=0, description="[편향⑤] 후회 회피 ρ_i: 준거점 초과 이득에 대한 불안·의심 강도 (기본 0.3)")

    # 6. 시기심·반응적 가치하락 (Envy & Reactive Devaluation) — hostility_AB 와 결합
    bias_beta: float = Field(0.5, ge=0, description="[편향⑥] 시기심·불평등 혐오 β_i: 상대방이 더 받을 때 느끼는 불쾌감 (기본 0.5)")

    # 7. 평판 위험·청중 효과 (Reputation Risk & Audience Effect)
    min_reputation_M: float = Field(..., ge=0, description="[편향⑦] 체면 마지노선 M_i: 이 값 미만 배분은 공개적 수용 불가")


class CoordinationRequest(BaseModel):
    conflict_type: str = Field(
        "예산 배분",
        description=(
            "갈등 유형 (예: '예산 배분', '사업 관할권', '인력 배분', '규제 권한', '정책 우선순위' 등). "
            "결과 해설문에 반영됩니다."
        ),
    )
    total_resource: float = Field(
        ..., gt=0,
        description=(
            "협상 대상 자원의 총량 (B). 예산이면 억 원 단위, "
            "관할권·우선순위이면 0~100 점수 척도로 입력하세요."
        ),
    )
    actor_A: Actor = Field(..., description="A측 행위자 정보 및 심리 프로파일")
    actor_B: Actor = Field(..., description="B측 행위자 정보 및 심리 프로파일")
    hostility_AB: float = Field(
        0.0, ge=0,
        description="[편향⑥] 행위자 간 대립도 H (0=중립, 높을수록 반응적 가치하락 심화)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "conflict_type": "예산 배분",
                "total_resource": 100,
                "actor_A": {
                    "name": "A부처",
                    "weight_w": 1.2,
                    "disagreement_d": 10,
                    "historical_x0": 50,
                    "bias_alpha": 1.1,
                    "bias_lambda": 2.2,
                    "bias_gamma": 0.3,
                    "bias_delta": 0.5,
                    "anchor_demand": None,
                    "bias_rho": 0.3,
                    "min_reputation_M": 40,
                },
                "actor_B": {
                    "name": "B부처",
                    "weight_w": 1.0,
                    "disagreement_d": 8,
                    "historical_x0": 50,
                    "bias_alpha": 1.1,
                    "bias_lambda": 2.0,
                    "bias_gamma": 0.4,
                    "bias_delta": 0.6,
                    "anchor_demand": None,
                    "bias_rho": 0.2,
                    "min_reputation_M": 35,
                },
                "hostility_AB": 0.2,
            }
        }
    }


class Allocation(BaseModel):
    actor_A_share: float = Field(..., description="A측 최적 배분량 (입력 단위 동일)")
    actor_B_share: float = Field(..., description="B측 최적 배분량 (입력 단위 동일)")


class Satisfaction(BaseModel):
    actor_A_utility: float = Field(..., description="A 부처 심리적 수정 효용값")
    actor_B_utility: float = Field(..., description="B 부처 심리적 수정 효용값")


class CoordinationResponse(BaseModel):
    status: str = Field(..., description="조정 결과 상태: success / infeasible / no_equilibrium")
    optimized_allocation: Allocation = Field(..., description="최적 예산 배분안")
    psychological_satisfaction: Satisfaction = Field(..., description="심리적 만족도")
    coordination_note: str = Field(..., description="조정 결과 자연어 해설")


# ---------------------------------------------------------------------------
# Module 2: 심리적 수정 효용 함수 엔진
# ---------------------------------------------------------------------------
def base_utility(x_i: float, alpha_i: float) -> float:
    """기본 효용 (자기고양 편향 반영): x_i * (2 - α_i).

    α_i 가 1보다 클수록 과도한 자기고양으로 실질 효용이 왜곡(감소)된다.
    """
    return x_i * (2.0 - alpha_i)


def loss_penalty(x_i: float, x0: float, lam_i: float) -> float:
    """손실 회피 페널티 (부존 효과·매몰비용 오류): λ_i * max(0, x_0 - x_i)."""
    return lam_i * max(0.0, x0 - x_i)


def envy_penalty(x_i: float, x_j: float, beta_i: float, hostility: float) -> float:
    """시기심 페널티 (불평등 혐오·반응적 가치하락):
    β_i * (1 + H_ij) * max(0, x_j - x_i).
    """
    return beta_i * (1.0 + hostility) * max(0.0, x_j - x_i)


def reputation_penalty(x_i: float, m_i: float) -> float:
    """[편향⑦] 체면 페널티 (청중 효과·평판 위험): x_i < M_i 이면 ∞(대용 상수), 아니면 0."""
    return REPUTATION_INF_PENALTY if x_i < m_i else 0.0


def fixed_pie_penalty(x_j: float, gamma_i: float) -> float:
    """[편향③] 고정된 파이 편향: γ_i * x_j
    상대방 몫 전체를 자신의 손실로 인식하는 제로섬 사고.
    β_i(시기심)가 x_j > x_i 일 때만 작동하는 것과 달리 x_j 자체를 페널티로 부과.
    """
    return gamma_i * x_j


def anchoring_penalty(x_i: float, anchor_i: float, delta_i: float) -> float:
    """[편향④] 앵커링 페널티: δ_i * max(0, a_i - x_i)
    첫 요구안(앵커) 아래로 내려가는 것에 대한 심리적 저항.
    """
    return delta_i * max(0.0, anchor_i - x_i)


def regret_penalty(x_i: float, x0: float, rho_i: float) -> float:
    """[편향⑤] 후회 회피 페널티: ρ_i * max(0, x_i - x_0)
    준거점보다 많이 받을수록 '더 받을 수 있었나' 의심·불안이 커져 효용이 감소.
    (승자의 저주: 너무 쉽게 타결되면 오히려 찝찝함)
    """
    return rho_i * max(0.0, x_i - x0)


def modified_utility(
    x_i: float, x_j: float, actor: Actor, hostility: float
) -> float:
    """행위자 i의 심리적 수정 효용 V_i(x_i, x_j) — 편향 7종 반영."""
    anchor = actor.anchor_demand if actor.anchor_demand is not None else actor.historical_x0 * 1.5
    return (
        base_utility(x_i, actor.bias_alpha)                                          # 편향①
        - loss_penalty(x_i, actor.historical_x0, actor.bias_lambda)                  # 편향②
        - fixed_pie_penalty(x_j, actor.bias_gamma)                                   # 편향③
        - anchoring_penalty(x_i, anchor, actor.bias_delta)                           # 편향④
        - regret_penalty(x_i, actor.historical_x0, actor.bias_rho)                   # 편향⑤
        - envy_penalty(x_i, x_j, actor.bias_beta, hostility)                         # 편향⑥
        - reputation_penalty(x_i, actor.min_reputation_M)                            # 편향⑦
    )


# ---------------------------------------------------------------------------
# Module 3: 내시 바게닝 최적화 솔버
# ---------------------------------------------------------------------------
def negative_nash_product(x_A: float, req: CoordinationRequest) -> float:
    """최소화 대상: -log(Nash Product).

    Nash Product = (V_A - d_A)^w_A * (V_B - d_B)^w_B
    로그 변환으로 수치 안정성을 확보하고, 잉여가 음수면 큰 페널티를 반환한다.
    """
    A, B = req.actor_A, req.actor_B
    x_B = req.total_resource - x_A

    V_A = modified_utility(x_A, x_B, A, req.hostility_AB)
    V_B = modified_utility(x_B, x_A, B, req.hostility_AB)

    surplus_A = V_A - A.disagreement_d
    surplus_B = V_B - B.disagreement_d

    # 결렬점 보장(V_i >= d_i) 위반 시 해를 강하게 배제
    if surplus_A <= SURPLUS_FLOOR or surplus_B <= SURPLUS_FLOOR:
        return REPUTATION_INF_PENALTY

    log_nash = A.weight_w * np.log(surplus_A) + B.weight_w * np.log(surplus_B)
    return -log_nash


def solve_coordination(req: CoordinationRequest) -> CoordinationResponse:
    A, B = req.actor_A, req.actor_B
    budget = req.total_resource

    # 탐색 구간: x_A ∈ [M_A, B - M_B]  (양측 체면 마지노선 보장)
    lower = A.min_reputation_M
    upper = budget - B.min_reputation_M

    if lower > upper:
        return CoordinationResponse(
            status="infeasible",
            optimized_allocation=Allocation(actor_A_share=0.0, actor_B_share=0.0),
            psychological_satisfaction=Satisfaction(
                actor_A_utility=0.0, actor_B_utility=0.0
            ),
            coordination_note=(
                f"[{req.conflict_type}] 체면 마지노선 합"
                f"({A.min_reputation_M}+{B.min_reputation_M})이 "
                f"총 자원({budget})을 초과하여 실행 가능한 조정안이 없습니다. "
                "패키지 딜(로그롤링) 등 추가 자원 탐색이 필요합니다."
            ),
        )

    result = minimize_scalar(
        negative_nash_product,
        bounds=(lower, upper),
        args=(req,),
        method="bounded",
        options={"xatol": 1e-6},
    )

    x_A = float(result.x)
    x_B = budget - x_A

    # 결렬점 위반 등으로 유효해를 찾지 못한 경우
    if (not result.success) or result.fun >= REPUTATION_INF_PENALTY:
        return CoordinationResponse(
            status="no_equilibrium",
            optimized_allocation=Allocation(
                actor_A_share=round(x_A, 2), actor_B_share=round(x_B, 2)
            ),
            psychological_satisfaction=Satisfaction(
                actor_A_utility=0.0, actor_B_utility=0.0
            ),
            coordination_note=(
                f"[{req.conflict_type}] 단일 자원 조정만으로는 양측 결렬점을 동시에 만족하는 "
                "내시균형이 도출되지 않았습니다. 패키지 딜(로그롤링)로 "
                "연관 자원을 리워드로 결합하는 2단계 중재를 권장합니다."
            ),
        )

    V_A = modified_utility(x_A, x_B, A, req.hostility_AB)
    V_B = modified_utility(x_B, x_A, B, req.hostility_AB)

    return CoordinationResponse(
        status="success",
        optimized_allocation=Allocation(
            actor_A_share=round(x_A, 2), actor_B_share=round(x_B, 2)
        ),
        psychological_satisfaction=Satisfaction(
            actor_A_utility=round(V_A, 2), actor_B_utility=round(V_B, 2)
        ),
        coordination_note=_build_note(req, x_A, x_B),
    )


def _build_note(req: CoordinationRequest, x_A: float, x_B: float) -> str:
    """조정 결과에 대한 자연어 해설 생성 (갈등 유형 및 7종 편향 반영)."""
    A, B = req.actor_A, req.actor_B
    parts: list[str] = []

    for actor, x in ((A, x_A), (B, x_B)):
        delta = x - actor.historical_x0
        if abs(delta) < 0.5:
            trend = f"준거점({actor.historical_x0:.0f}) 수준 유지"
        elif delta > 0:
            trend = f"준거점({actor.historical_x0:.0f}) 대비 +{delta:.1f} 증가"
        else:
            trend = f"준거점({actor.historical_x0:.0f}) 대비 {delta:.1f} 감소"
        parts.append(f"{actor.name}: {x:.1f} ({trend})")

    dominant_biases: list[str] = []
    high_lambda = max((A, B), key=lambda a: a.bias_lambda)
    dominant_biases.append(f"{high_lambda.name}의 손실회피(λ={high_lambda.bias_lambda})")

    high_gamma = max((A, B), key=lambda a: a.bias_gamma)
    if high_gamma.bias_gamma > 0.2:
        dominant_biases.append(f"{high_gamma.name}의 고정된 파이 편향(γ={high_gamma.bias_gamma})")

    high_delta = max((A, B), key=lambda a: a.bias_delta)
    if high_delta.bias_delta > 0.3:
        dominant_biases.append(f"{high_delta.name}의 앵커링 효과(δ={high_delta.bias_delta})")

    note = (
        f"[{req.conflict_type}] " + " / ".join(parts)
        + f". 주요 심리 편향: {', '.join(dominant_biases)}을 반영해 "
        f"체면 마지노선(M_A={A.min_reputation_M:.0f}, M_B={B.min_reputation_M:.0f})을 "
        "준수하는 최소 저항 조정안입니다."
    )
    if req.hostility_AB > 0:
        note += f" 행위자 간 대립도(H={req.hostility_AB})로 인한 반응적 가치하락 가중 반영."
    return note


# ---------------------------------------------------------------------------
# Module 4: FastAPI 인터페이스
# ---------------------------------------------------------------------------

태그_메타데이터 = [
    {
        "name": "조정 엔진",
        "description": (
            "두 행위자의 심리 파라미터를 입력하면 **내시 바게닝 최적화**를 통해 "
            "양측의 심리적 저항을 최소화하는 최적 배분안을 자동 산출합니다. "
            "예산·관할권·인력·규제권한 등 모든 단일 축 갈등에 적용 가능합니다."
        ),
    },
    {
        "name": "시스템",
        "description": "서버 상태 확인용 엔드포인트입니다.",
    },
]

사용설명서 = """
## 이 엔진이 하는 일

두 기관이 무엇인가를 두고 다툴 때, 양측의 **심리적 저항을 최소화하는 조정안**을 자동으로 계산합니다.

예산뿐 아니라 **사업 관할권, 인력 배분, 규제 권한, 정책 우선순위** 등 수치로 표현할 수 있는 모든 갈등에 적용됩니다.

---

## 사용 방법 (5단계)

### 1단계 — 엔드포인트 열기

이 페이지에서 아래로 스크롤하면 초록색 **`POST /api/v1/coordination/solve`** 버튼이 보입니다. 클릭하세요.

### 2단계 — 입력 화면 열기

오른쪽에 나타나는 **`Try it out`** 버튼을 클릭하세요.
그러면 JSON 입력창이 열리고, 예시 데이터가 자동으로 채워져 있습니다.

### 3단계 — 갈등 상황 입력

입력창의 JSON을 실제 상황에 맞게 수정합니다.

**먼저 이 세 가지를 설정하세요:**

```
conflict_type   : 갈등 유형을 한 문장으로 적습니다.
                  예) "예산 배분", "사업 관할권", "인력 배분", "규제 권한"

total_resource  : 두 기관이 나눌 자원의 총량입니다.
                  예산이면 총 예산액, 관할권이면 100(점 척도), 인력이면 총 인원 수

hostility_AB    : 두 기관 사이의 감정적 대립 정도입니다.
                  0 = 중립, 0.5 = 보통 갈등, 1.0 이상 = 심각한 적대 관계
```

**그 다음, 각 기관(actor_A, actor_B)의 정보를 입력하세요:**

```
name            : 기관 이름
weight_w        : 이 기관의 협상력 (더 강한 쪽을 높게 설정, 예: 1.2)
disagreement_d  : 협상이 완전히 결렬됐을 때 이 기관이 입는 피해 수치
historical_x0   : 현재 이 기관이 갖고 있는 몫 (예: 현재 예산, 현재 점유율)
min_reputation_M: 이 기관이 체면상 절대 양보할 수 없는 최솟값
```

**심리 편향 계수는 기본값을 그대로 써도 됩니다. 조정이 필요할 때만 바꾸세요:**

```
bias_alpha  : 자기 능력을 과신하는 정도 (기본 1.1, 클수록 자기고양 심함)
bias_lambda : 손해에 민감한 정도 (기본 2.2, 클수록 잃는 걸 극도로 싫어함)
bias_gamma  : 상대방 이득을 내 손실로 여기는 정도 (기본 0.3, 제로섬 사고)
bias_delta  : 처음 요구한 숫자에 얼마나 집착하는지 (기본 0.5, 앵커링)
anchor_demand: 처음 요구한 숫자 (비워두면 historical_x0 × 1.5 자동 적용)
bias_rho    : 너무 쉽게 이겼을 때 찝찝함을 느끼는 정도 (기본 0.3, 후회 회피)
```

### 4단계 — 실행

파란색 **`Execute`** 버튼을 클릭합니다.

### 5단계 — 결과 확인

`Execute` 아래 **`Response body`** 에 결과가 나타납니다.

```
status
  "success"        → 조정안 도출 성공
  "infeasible"     → 양측 최솟값 합이 총 자원 초과. 자원을 늘리거나 다른 조건을 묶어야 함
  "no_equilibrium" → 이 자원만으로는 합의점 없음. 연관 자원을 함께 협상해야 함

optimized_allocation
  actor_A_share    → A 기관에 배분할 최적 수치
  actor_B_share    → B 기관에 배분할 최적 수치
  (단위는 total_resource 입력값과 동일)

psychological_satisfaction
  actor_A_utility  → A 기관의 심리적 만족도 (양수일수록 수용 가능성 높음)
  actor_B_utility  → B 기관의 심리적 만족도 (양수일수록 수용 가능성 높음)

coordination_note
  → 결과를 한국어로 설명한 요약문
```

---

## 갈등 유형별 입력 기준

| 갈등 유형 | total_resource | historical_x0 |
|-----------|---------------|---------------|
| 예산 배분 | 총 예산액 | 현재 배분액 |
| 사업 관할권 | 100 | 현재 담당 비중(0~100) |
| 인력 배분 | 총 정원 수 | 현재 인원 수 |
| 규제 권한 | 100 | 현재 권한 점수(0~100) |
| 정책 우선순위 | 100 | 현재 우선순위 점수(0~100) |
"""

app = FastAPI(
    title="Project HARMONIA — 다부처 갈등 조정 엔진",
    description=사용설명서,
    version="1.0.0",
    openapi_tags=태그_메타데이터,
)


HARMONIA_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HARMONIA — 부처 간 갈등 조정 엔진</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f8;color:#1a2332}
header{background:#1e3a5f;color:#fff;padding:24px 32px}
header h1{font-size:1.5rem;font-weight:700;margin-bottom:4px}
header p{font-size:.9rem;opacity:.75}
main{max-width:980px;margin:28px auto;padding:0 16px 60px}
.card{background:#fff;border-radius:12px;padding:24px;margin-bottom:22px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.card h2{font-size:1rem;font-weight:700;color:#1e3a5f;margin-bottom:18px;display:flex;align-items:center;gap:8px}
.badge{background:#1e3a5f;color:#fff;border-radius:50%;width:22px;height:22px;display:inline-flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;flex-shrink:0}
/* 갈등 유형 */
.conflict-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.ccard{border:2px solid #e2e8f0;border-radius:10px;padding:14px 10px;text-align:center;cursor:pointer;transition:all .15s}
.ccard:hover{border-color:#3b82f6;background:#eff6ff}
.ccard.on{border-color:#1e3a5f;background:#dbeafe}
.ccard .ico{font-size:1.8rem;margin-bottom:6px}
.ccard .lbl{font-size:.82rem;font-weight:600;color:#374151}
.ccard .sub{font-size:.72rem;color:#9ca3af;margin-top:3px}
/* 폼 */
.row2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px}
@media(max-width:560px){.row2{grid-template-columns:1fr}}
.actors{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:640px){.actors{grid-template-columns:1fr}}
.apanel{border:2px solid #e2e8f0;border-radius:10px;padding:18px}
.apanel.pa{border-color:#3b82f6}.apanel.pb{border-color:#ef4444}
.apanel h3{font-size:.95rem;font-weight:700;margin-bottom:14px}
.pa h3{color:#2563eb}.pb h3{color:#dc2626}
.f{margin-bottom:12px}
.f label{display:block;font-size:.78rem;font-weight:600;color:#374151;margin-bottom:5px}
.f .tip{font-size:.7rem;color:#9ca3af;margin-top:3px}
.f input[type=text],.f input[type=number]{width:100%;border:1.5px solid #d1d5db;border-radius:7px;padding:7px 10px;font-size:.88rem;outline:none}
.f input:focus{border-color:#3b82f6}
.sf{margin-bottom:12px}
.sf .sl{display:flex;justify-content:space-between;font-size:.78rem;font-weight:600;color:#374151;margin-bottom:5px}
.sf .sl span{color:#6b7280;font-weight:400;font-size:.82rem}
.sf input[type=range]{width:100%;accent-color:#1e3a5f}
.sf .tip{font-size:.7rem;color:#9ca3af;margin-top:3px}
/* 고급 설정 */
details{margin-bottom:22px}
details summary{cursor:pointer;font-size:.88rem;font-weight:600;color:#1e3a5f;padding:11px 16px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;user-select:none}
details summary::marker{display:none}
details summary::before{content:"▶  "}
details[open] summary::before{content:"▼  "}
.bgrid{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:18px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;background:#fff}
@media(max-width:640px){.bgrid{grid-template-columns:1fr}}
/* 실행 버튼 */
#runBtn{width:100%;padding:15px;background:#1e3a5f;color:#fff;border:none;border-radius:10px;font-size:1.05rem;font-weight:700;cursor:pointer;transition:background .2s;margin-bottom:22px}
#runBtn:hover{background:#2d5a8e}
#runBtn:disabled{background:#9ca3af;cursor:not-allowed}
/* 결과 */
#results{display:none}
.sbadge{display:inline-block;padding:6px 14px;border-radius:20px;font-size:.85rem;font-weight:700;margin-bottom:18px}
.ss{background:#d1fae5;color:#065f46}.si{background:#fee2e2;color:#991b1b}.sn{background:#fef3c7;color:#92400e}
.bar-wrap{margin-bottom:20px}
.bar-track{height:48px;border-radius:8px;overflow:hidden;display:flex;margin-bottom:8px}
.ba{background:#2563eb;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:.85rem;transition:width .7s ease;white-space:nowrap;overflow:hidden;padding:0 6px}
.bb{background:#ef4444;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:.85rem;transition:width .7s ease;white-space:nowrap;overflow:hidden;padding:0 6px}
.bar-lbl{display:flex;justify-content:space-between;font-size:.83rem;color:#374151}
.util-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px}
.uc{border-radius:8px;padding:14px;text-align:center}
.ua{background:#eff6ff;border:1px solid #bfdbfe}.ub{background:#fef2f2;border:1px solid #fecaca}
.uc .sc{font-size:1.5rem;font-weight:700;margin-bottom:4px}
.ua .sc{color:#2563eb}.ub .sc{color:#dc2626}
.uc .lc{font-size:.78rem;color:#6b7280}
.note{background:#f8fafc;border-left:4px solid #1e3a5f;padding:14px 16px;border-radius:0 8px 8px 0;font-size:.88rem;line-height:1.7;color:#374151}
</style>
</head>
<body>
<header>
  <h1>HARMONIA — 부처 간 갈등 조정 엔진</h1>
  <p>심리적 편향 7종을 반영한 내시 바게닝 기반 갈등 조정 시스템</p>
</header>
<main>

<!-- 1단계: 갈등 유형 -->
<div class="card">
  <h2><span class="badge">1</span> 어떤 갈등인가요?</h2>
  <div class="conflict-grid" id="cg">
    <div class="ccard on" data-type="예산 배분" data-unit="억 원" data-x0hint="현재 배분액 (억 원)" onclick="pick(this)">
      <div class="ico">💰</div><div class="lbl">예산 배분</div><div class="sub">재원 배분 갈등</div>
    </div>
    <div class="ccard" data-type="사업 관할권" data-unit="점 (0~100)" data-x0hint="현재 담당 비중 (0~100)" onclick="pick(this)">
      <div class="ico">🗺️</div><div class="lbl">사업 관할권</div><div class="sub">업무 영역 갈등</div>
    </div>
    <div class="ccard" data-type="인력 배분" data-unit="명" data-x0hint="현재 인원 수 (명)" onclick="pick(this)">
      <div class="ico">👥</div><div class="lbl">인력 배분</div><div class="sub">정원·조직 갈등</div>
    </div>
    <div class="ccard" data-type="규제 권한" data-unit="점 (0~100)" data-x0hint="현재 권한 점수 (0~100)" onclick="pick(this)">
      <div class="ico">⚖️</div><div class="lbl">규제 권한</div><div class="sub">심의·규제 갈등</div>
    </div>
    <div class="ccard" data-type="정책 우선순위" data-unit="점 (0~100)" data-x0hint="현재 우선순위 점수 (0~100)" onclick="pick(this)">
      <div class="ico">📋</div><div class="lbl">정책 우선순위</div><div class="sub">정책 비중 갈등</div>
    </div>
  </div>
</div>

<!-- 2단계: 기본 설정 -->
<div class="card">
  <h2><span class="badge">2</span> 기본 정보 입력</h2>
  <div class="row2">
    <div class="f">
      <label id="trLabel">총 자원 (억 원)</label>
      <input type="number" id="tr" value="100" min="1">
      <div class="tip">두 기관이 나눠 가질 자원의 총량</div>
    </div>
    <div class="sf">
      <div class="sl">두 기관의 대립 강도 <span id="hv">0.2</span></div>
      <input type="range" id="host" min="0" max="2" step="0.1" value="0.2" oninput="sv('hv',this.value)">
      <div class="tip">0 = 중립 &nbsp;|&nbsp; 0.5 = 보통 갈등 &nbsp;|&nbsp; 1.0 이상 = 심각한 적대</div>
    </div>
  </div>

  <div class="actors">
    <div class="apanel pa">
      <h3>🔵 A 기관</h3>
      <div class="f"><label>기관 이름</label><input type="text" id="an" value="A부처"></div>
      <div class="f">
        <label id="ax0lbl">현재 점유량 (억 원)</label>
        <input type="number" id="ax0" value="50">
        <div class="tip" id="ax0tip">현재 배분액 (억 원)</div>
      </div>
      <div class="f">
        <label>절대 양보 불가 최솟값</label>
        <input type="number" id="aM" value="40">
        <div class="tip">이 수치 이하는 체면상 공개적으로 수용 불가</div>
      </div>
      <div class="sf">
        <div class="sl">협상력 <span id="awv">1.2</span></div>
        <input type="range" id="aw" min="0.5" max="3" step="0.1" value="1.2" oninput="sv('awv',this.value)">
        <div class="tip">상대보다 강하면 높게, 대등하면 1.0</div>
      </div>
      <div class="sf">
        <div class="sl">협상 결렬 시 피해 <span id="adv">10</span></div>
        <input type="range" id="ad" min="0" max="50" step="1" value="10" oninput="sv('adv',this.value)">
        <div class="tip">협상이 완전히 깨졌을 때 이 기관이 입는 손해</div>
      </div>
    </div>

    <div class="apanel pb">
      <h3>🔴 B 기관</h3>
      <div class="f"><label>기관 이름</label><input type="text" id="bn" value="B부처"></div>
      <div class="f">
        <label id="bx0lbl">현재 점유량 (억 원)</label>
        <input type="number" id="bx0" value="50">
        <div class="tip" id="bx0tip">현재 배분액 (억 원)</div>
      </div>
      <div class="f">
        <label>절대 양보 불가 최솟값</label>
        <input type="number" id="bM" value="35">
        <div class="tip">이 수치 이하는 체면상 공개적으로 수용 불가</div>
      </div>
      <div class="sf">
        <div class="sl">협상력 <span id="bwv">1.0</span></div>
        <input type="range" id="bw" min="0.5" max="3" step="0.1" value="1.0" oninput="sv('bwv',this.value)">
        <div class="tip">상대보다 강하면 높게, 대등하면 1.0</div>
      </div>
      <div class="sf">
        <div class="sl">협상 결렬 시 피해 <span id="bdv">8</span></div>
        <input type="range" id="bd" min="0" max="50" step="1" value="8" oninput="sv('bdv',this.value)">
        <div class="tip">협상이 완전히 깨졌을 때 이 기관이 입는 손해</div>
      </div>
    </div>
  </div>
</div>

<!-- 3단계: 심리 편향 (선택) -->
<details>
  <summary>3단계 (선택사항) — 심리 편향 세부 조정 &nbsp; <small style="font-weight:400;color:#6b7280">기본값으로도 충분합니다</small></summary>
  <div class="bgrid">
    <div>
      <div style="font-size:.85rem;font-weight:700;color:#2563eb;margin-bottom:12px">🔵 A 기관</div>
      <div class="sf"><div class="sl">① 자기고양 (α) <span id="aalv">1.1</span></div><input type="range" id="aal" min="1" max="2" step="0.05" value="1.1" oninput="sv('aalv',this.value)"><div class="tip">자기 기여를 과대평가할수록 높게</div></div>
      <div class="sf"><div class="sl">② 손실 회피 (λ) <span id="allv">2.2</span></div><input type="range" id="all" min="0" max="5" step="0.1" value="2.2" oninput="sv('allv',this.value)"><div class="tip">잃는 것을 극도로 싫어할수록 높게</div></div>
      <div class="sf"><div class="sl">③ 제로섬 사고 (γ) <span id="aglv">0.3</span></div><input type="range" id="agl" min="0" max="1" step="0.05" value="0.3" oninput="sv('aglv',this.value)"><div class="tip">상대방 이득을 내 손실로 볼수록 높게</div></div>
      <div class="sf"><div class="sl">④ 앵커링 (δ) <span id="adlv">0.5</span></div><input type="range" id="adl" min="0" max="2" step="0.05" value="0.5" oninput="sv('adlv',this.value)"><div class="tip">첫 요구안에 집착할수록 높게</div></div>
      <div class="sf"><div class="sl">⑤ 후회 회피 (ρ) <span id="arlv">0.3</span></div><input type="range" id="arl" min="0" max="1" step="0.05" value="0.3" oninput="sv('arlv',this.value)"><div class="tip">이겨도 찝찝함을 느낄수록 높게</div></div>
      <div class="sf"><div class="sl">⑥ 시기심 (β) <span id="ablv">0.5</span></div><input type="range" id="abl" min="0" max="2" step="0.05" value="0.5" oninput="sv('ablv',this.value)"><div class="tip">상대방이 더 받을 때 불쾌함이 클수록 높게</div></div>
    </div>
    <div>
      <div style="font-size:.85rem;font-weight:700;color:#dc2626;margin-bottom:12px">🔴 B 기관</div>
      <div class="sf"><div class="sl">① 자기고양 (α) <span id="balv">1.1</span></div><input type="range" id="bal" min="1" max="2" step="0.05" value="1.1" oninput="sv('balv',this.value)"><div class="tip">자기 기여를 과대평가할수록 높게</div></div>
      <div class="sf"><div class="sl">② 손실 회피 (λ) <span id="bllv">2.0</span></div><input type="range" id="bll" min="0" max="5" step="0.1" value="2.0" oninput="sv('bllv',this.value)"><div class="tip">잃는 것을 극도로 싫어할수록 높게</div></div>
      <div class="sf"><div class="sl">③ 제로섬 사고 (γ) <span id="bglv">0.4</span></div><input type="range" id="bgl" min="0" max="1" step="0.05" value="0.4" oninput="sv('bglv',this.value)"><div class="tip">상대방 이득을 내 손실로 볼수록 높게</div></div>
      <div class="sf"><div class="sl">④ 앵커링 (δ) <span id="bdlv">0.6</span></div><input type="range" id="bdl" min="0" max="2" step="0.05" value="0.6" oninput="sv('bdlv',this.value)"><div class="tip">첫 요구안에 집착할수록 높게</div></div>
      <div class="sf"><div class="sl">⑤ 후회 회피 (ρ) <span id="brlv">0.2</span></div><input type="range" id="brl" min="0" max="1" step="0.05" value="0.2" oninput="sv('brlv',this.value)"><div class="tip">이겨도 찝찝함을 느낄수록 높게</div></div>
      <div class="sf"><div class="sl">⑥ 시기심 (β) <span id="bblv">0.6</span></div><input type="range" id="bbl" min="0" max="2" step="0.05" value="0.6" oninput="sv('bblv',this.value)"><div class="tip">상대방이 더 받을 때 불쾌함이 클수록 높게</div></div>
    </div>
  </div>
</details>

<!-- 실행 -->
<button id="runBtn" onclick="run()">⚖️ 갈등 조정 실행</button>

<!-- 결과 -->
<div class="card" id="results">
  <h2>조정 결과</h2>
  <div id="sb"></div>
  <div class="bar-wrap">
    <div class="bar-track"><div class="ba" id="ba">A</div><div class="bb" id="bb">B</div></div>
    <div class="bar-lbl"><span id="bla"></span><span id="blb"></span></div>
  </div>
  <div class="util-row">
    <div class="uc ua"><div class="sc" id="ua">—</div><div class="lc" id="ula">A 기관 심리적 수용도</div></div>
    <div class="uc ub"><div class="sc" id="ub">—</div><div class="lc" id="ulb">B 기관 심리적 수용도</div></div>
  </div>
  <div class="note" id="note"></div>
</div>

</main>
<script>
let CT={type:'예산 배분',unit:'억 원',x0hint:'현재 배분액 (억 원)'};
function sv(id,v){document.getElementById(id).textContent=v}
function pick(el){
  document.querySelectorAll('.ccard').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  CT={type:el.dataset.type,unit:el.dataset.unit,x0hint:el.dataset.x0hint};
  document.getElementById('trLabel').textContent='총 자원 ('+CT.unit+')';
  document.getElementById('ax0lbl').textContent='현재 점유량 ('+CT.unit+')';
  document.getElementById('bx0lbl').textContent='현재 점유량 ('+CT.unit+')';
  document.getElementById('ax0tip').textContent=CT.x0hint;
  document.getElementById('bx0tip').textContent=CT.x0hint;
}
async function run(){
  const btn=document.getElementById('runBtn');
  btn.disabled=true; btn.textContent='계산 중...';
  const p={
    conflict_type:CT.type,
    total_resource:+document.getElementById('tr').value,
    hostility_AB:+document.getElementById('host').value,
    actor_A:{
      name:document.getElementById('an').value,
      weight_w:+document.getElementById('aw').value,
      disagreement_d:+document.getElementById('ad').value,
      historical_x0:+document.getElementById('ax0').value,
      min_reputation_M:+document.getElementById('aM').value,
      bias_alpha:+document.getElementById('aal').value,
      bias_lambda:+document.getElementById('all').value,
      bias_gamma:+document.getElementById('agl').value,
      bias_delta:+document.getElementById('adl').value,
      bias_rho:+document.getElementById('arl').value,
      bias_beta:+document.getElementById('abl').value,
    },
    actor_B:{
      name:document.getElementById('bn').value,
      weight_w:+document.getElementById('bw').value,
      disagreement_d:+document.getElementById('bd').value,
      historical_x0:+document.getElementById('bx0').value,
      min_reputation_M:+document.getElementById('bM').value,
      bias_alpha:+document.getElementById('bal').value,
      bias_lambda:+document.getElementById('bll').value,
      bias_gamma:+document.getElementById('bgl').value,
      bias_delta:+document.getElementById('bdl').value,
      bias_rho:+document.getElementById('brl').value,
      bias_beta:+document.getElementById('bbl').value,
    }
  };
  try{
    const r=await fetch('/api/v1/coordination/solve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
    show(await r.json(),p);
  }catch(e){alert('오류: '+e.message);}
  finally{btn.disabled=false;btn.textContent='⚖️ 갈등 조정 실행';}
}
function show(d,p){
  const el=document.getElementById('results');
  el.style.display='block';
  el.scrollIntoView({behavior:'smooth'});
  const sm={success:{c:'ss',t:'✅ 조정안 도출 성공'},infeasible:{c:'si',t:'❌ 조정 불가 — 추가 자원 협상 필요'},no_equilibrium:{c:'sn',t:'⚠️ 단일 자원으로 균형 불가 — 2단계 중재 필요'}};
  const s=sm[d.status]||{c:'',t:d.status};
  document.getElementById('sb').innerHTML=`<span class="sbadge ${s.c}">${s.t}</span>`;
  const tot=p.total_resource, aS=d.optimized_allocation.actor_A_share, bS=d.optimized_allocation.actor_B_share;
  const aN=p.actor_A.name, bN=p.actor_B.name, u=CT.unit;
  const ap=(aS/tot*100).toFixed(1), bp=(bS/tot*100).toFixed(1);
  document.getElementById('ba').style.width=ap+'%'; document.getElementById('ba').textContent=`${aN}  ${aS} ${u}`;
  document.getElementById('bb').style.width=bp+'%'; document.getElementById('bb').textContent=`${bN}  ${bS} ${u}`;
  document.getElementById('bla').textContent=`${aN}: ${aS} ${u} (${ap}%)`;
  document.getElementById('blb').textContent=`${bN}: ${bS} ${u} (${bp}%)`;
  document.getElementById('ua').textContent=d.psychological_satisfaction.actor_A_utility;
  document.getElementById('ub').textContent=d.psychological_satisfaction.actor_B_utility;
  document.getElementById('ula').textContent=aN+' 심리적 수용도';
  document.getElementById('ulb').textContent=bN+' 심리적 수용도';
  document.getElementById('note').textContent=d.coordination_note;
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, tags=["시스템"], summary="조정 엔진 UI", include_in_schema=False)
def root() -> HTMLResponse:
    return HTMLResponse(content=HARMONIA_HTML)


@app.get("/health", tags=["시스템"], summary="서버 상태 확인")
def health() -> dict:
    return {"status": "ok", "project": "HARMONIA", "api": "/api/v1/coordination/solve"}


@app.post(
    "/api/v1/coordination/solve",
    response_model=CoordinationResponse,
    tags=["조정 엔진"],
    summary="부처 간 갈등 조정 실행",
    description=(
        "두 행위자의 심리 프로파일과 자원 제약을 입력하면 "
        "심리적 편향 7종을 반영한 내시 바게닝으로 최적 배분안(x_A*, x_B*)을 반환합니다. "
        "예산·관할권·인력·규제권한 등 모든 단일 축 갈등에 적용 가능합니다."
    ),
)
def solve(req: CoordinationRequest) -> CoordinationResponse:
    return solve_coordination(req)


# ---------------------------------------------------------------------------
# 단독 실행 데모 (서버 없이 솔버 직접 호출)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    print("=== 데모 1: 예산 배분 갈등 ===")
    demo_budget = CoordinationRequest(
        conflict_type="예산 배분",
        total_resource=100,
        actor_A=Actor(
            name="기획재정부",
            weight_w=1.2, disagreement_d=10, historical_x0=50,
            bias_alpha=1.1, bias_lambda=2.2, bias_gamma=0.3,
            bias_delta=0.5, bias_rho=0.3, min_reputation_M=40,
        ),
        actor_B=Actor(
            name="과학기술부",
            weight_w=1.0, disagreement_d=8, historical_x0=50,
            bias_alpha=1.1, bias_lambda=2.0, bias_gamma=0.4,
            bias_delta=0.6, bias_rho=0.2, min_reputation_M=35,
        ),
        hostility_AB=0.2,
    )
    print(json.dumps(solve_coordination(demo_budget).model_dump(), ensure_ascii=False, indent=2))

    print("\n=== 데모 2: 사업 관할권 갈등 (0~100점 척도) ===")
    demo_jurisdiction = CoordinationRequest(
        conflict_type="사업 관할권",
        total_resource=100,
        actor_A=Actor(
            name="환경부",
            weight_w=1.0, disagreement_d=5, historical_x0=60,
            bias_alpha=1.05, bias_lambda=2.5, bias_gamma=0.5,
            bias_delta=0.7, bias_rho=0.1, min_reputation_M=45,
        ),
        actor_B=Actor(
            name="산업통상자원부",
            weight_w=1.1, disagreement_d=5, historical_x0=40,
            bias_alpha=1.15, bias_lambda=2.0, bias_gamma=0.3,
            bias_delta=0.4, bias_rho=0.4, min_reputation_M=30,
        ),
        hostility_AB=0.5,
    )
    print(json.dumps(solve_coordination(demo_jurisdiction).model_dump(), ensure_ascii=False, indent=2))
