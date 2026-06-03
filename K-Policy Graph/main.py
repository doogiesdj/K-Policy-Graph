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
<title>갈등 조정 시스템 — HARMONIA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans KR','Segoe UI',sans-serif;background:#f5f7fa;color:#1f2937;font-size:15px;line-height:1.6}
.site-hd{background:#1e3a5f;color:#fff;padding:28px 32px;text-align:center}
.site-hd h1{font-size:1.7rem;font-weight:800;margin-bottom:6px}
.site-hd p{font-size:.95rem;opacity:.8;max-width:540px;margin:0 auto}
.wrap{max-width:820px;margin:28px auto;padding:0 16px 80px}
/* 카드 */
.card{background:#fff;border-radius:14px;padding:28px;margin-bottom:20px;box-shadow:0 2px 12px rgba(0,0,0,.07)}
.card-title{display:flex;align-items:center;gap:12px;margin-bottom:22px}
.sn{background:#1e3a5f;color:#fff;border-radius:50%;width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;font-size:.82rem;font-weight:800;flex-shrink:0}
.card-title h2{font-size:1.05rem;font-weight:700;color:#1e3a5f}
.card-title .sub{font-size:.82rem;color:#6b7280;margin-left:4px}
/* 갈등 유형 */
.type-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px}
.tc{border:2px solid #e5e7eb;border-radius:12px;padding:18px 12px;text-align:center;cursor:pointer;transition:all .15s;background:#fff}
.tc:hover{border-color:#3b82f6;background:#eff6ff;transform:translateY(-2px)}
.tc.on{border-color:#1e3a5f;background:#dbeafe}
.tc .ico{font-size:2rem;margin-bottom:8px}
.tc .nm{font-size:.88rem;font-weight:700;color:#374151}
.tc .ds{font-size:.74rem;color:#9ca3af;margin-top:4px;line-height:1.3}
/* 필드 */
.field{margin-bottom:18px}
.field label{display:block;font-size:.83rem;font-weight:700;color:#374151;margin-bottom:7px}
.field .desc{font-size:.75rem;color:#9ca3af;margin-top:4px}
.field input[type=text],.field input[type=number]{width:100%;border:2px solid #e5e7eb;border-radius:9px;padding:10px 14px;font-size:.95rem;outline:none;transition:border-color .2s;background:#fff}
.field input:focus{border-color:#3b82f6}
/* 슬라이더 */
.sfield{margin-bottom:18px}
.sfield .lrow{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.sfield .lt{font-size:.83rem;font-weight:700;color:#374151}
.sfield .lv{font-size:.83rem;background:#f1f5f9;padding:2px 10px;border-radius:12px;color:#1e3a5f;font-weight:700}
.sfield input[type=range]{width:100%;accent-color:#1e3a5f;cursor:pointer}
.sfield .ep{display:flex;justify-content:space-between;font-size:.72rem;color:#9ca3af;margin-top:4px}
/* 두 기관 나란히 */
.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:600px){.two{grid-template-columns:1fr}}
.inst{border:2px solid #e5e7eb;border-radius:12px;padding:20px}
.inst.ia{border-color:#3b82f6}.inst.ib{border-color:#ef4444}
.inst h3{font-size:.95rem;font-weight:800;margin-bottom:18px;padding-bottom:10px;border-bottom:1px solid #f3f4f6}
.ia h3{color:#2563eb}.ib h3{color:#dc2626}
/* 고급 */
details{background:#fff;border-radius:14px;margin-bottom:20px;box-shadow:0 2px 12px rgba(0,0,0,.07);overflow:hidden}
details summary{padding:18px 24px;cursor:pointer;font-size:.92rem;font-weight:700;color:#1e3a5f;list-style:none;display:flex;align-items:center;gap:8px}
details summary::before{content:"▶";font-size:.72rem;transition:transform .2s}
details[open] summary::before{transform:rotate(90deg)}
.adv-body{padding:0 24px 24px;border-top:1px solid #f3f4f6}
.adv-note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;font-size:.82rem;color:#92400e;margin:16px 0}
.bcols{display:grid;grid-template-columns:1fr 1fr;gap:24px}
@media(max-width:600px){.bcols{grid-template-columns:1fr}}
.bcol h4{font-size:.88rem;font-weight:800;margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid}
.bca h4{color:#2563eb;border-color:#3b82f6}.bcb h4{color:#dc2626;border-color:#ef4444}
/* 실행 버튼 */
.run-wrap{text-align:center;margin:4px 0 24px}
.run-btn{background:#1e3a5f;color:#fff;border:none;border-radius:12px;padding:17px 52px;font-size:1.1rem;font-weight:800;cursor:pointer;box-shadow:0 4px 16px rgba(30,58,95,.3);transition:all .2s}
.run-btn:hover{background:#2d5a8e;transform:translateY(-2px)}
.run-btn:disabled{background:#9ca3af;transform:none;box-shadow:none;cursor:not-allowed}
/* 결과 */
#results{display:none}
.rst{display:flex;align-items:flex-start;gap:12px;padding:16px 20px;border-radius:10px;margin-bottom:22px;font-size:.95rem;font-weight:600}
.rs-ok{background:#d1fae5;color:#065f46;border:1px solid #a7f3d0}
.rs-no{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5}
.rs-wn{background:#fef3c7;color:#92400e;border:1px solid #fde68a}
.bar-section{margin-bottom:22px}
.sec-label{font-size:.78rem;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}
.alloc-bar{height:56px;border-radius:10px;display:flex;overflow:hidden;margin-bottom:12px}
.aa{background:#2563eb;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:.88rem;transition:width .8s ease;overflow:hidden;padding:0 8px;white-space:nowrap}
.ab{background:#ef4444;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:.88rem;transition:width .8s ease;overflow:hidden;padding:0 8px;white-space:nowrap}
.alloc-cards{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.ac{border-radius:10px;padding:16px 18px}
.aca{background:#eff6ff;border:1px solid #bfdbfe}.acb{background:#fef2f2;border:1px solid #fecaca}
.ac .on{font-size:.8rem;color:#6b7280;margin-bottom:4px}
.ac .num{font-size:1.5rem;font-weight:800;margin-bottom:2px}
.aca .num{color:#2563eb}.acb .num{color:#dc2626}
.ac .pct{font-size:.8rem;color:#6b7280}
.util-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}
.uc{border-radius:10px;padding:16px;text-align:center}
.uca{background:#eff6ff;border:1px solid #bfdbfe}.ucb{background:#fef2f2;border:1px solid #fecaca}
.uc .ul{font-size:.78rem;color:#6b7280;margin-bottom:6px}
.uc .us{font-size:1.4rem;font-weight:800;margin-bottom:4px}
.uca .us{color:#2563eb}.ucb .us{color:#dc2626}
.uc .ui{font-size:.78rem;color:#374151}
.note-box{background:#f8fafc;border-left:4px solid #1e3a5f;border-radius:0 10px 10px 0;padding:16px 18px}
.note-box .nt{font-size:.75rem;font-weight:700;color:#1e3a5f;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
.note-box .nc{font-size:.9rem;line-height:1.75;color:#374151}
</style>
</head>
<body>

<div class="site-hd">
  <h1>🤝 부처·기관 간 갈등 조정 시스템</h1>
  <p>상황을 입력하면 양측이 받아들일 수 있는 최적 합의안을 찾아드립니다</p>
</div>

<div class="wrap">

<!-- 1. 갈등 유형 -->
<div class="card">
  <div class="card-title"><div class="sn">1</div><h2>어떤 문제를 해결하려 하시나요?</h2></div>
  <div class="type-grid" id="tg">
    <div class="tc on" data-type="예산 배분" data-unit="억 원" data-hint="두 기관이 나눌 총 예산액" data-ph="예) 100억이면 100" data-x0="이 기관이 현재 받고 있는 예산액" onclick="pick(this)">
      <div class="ico">💰</div><div class="nm">예산 배분</div><div class="ds">예산을 나누는 문제</div>
    </div>
    <div class="tc" data-type="사업 관할권" data-unit="점" data-hint="두 기관이 나눌 총 점수 (보통 100)" data-ph="예) 100" data-x0="이 기관이 현재 담당하는 비중 (0~100)" onclick="pick(this)">
      <div class="ico">🗺️</div><div class="nm">사업 관할권</div><div class="ds">어느 기관이 담당할지의 문제</div>
    </div>
    <div class="tc" data-type="인력 배분" data-unit="명" data-hint="두 기관이 나눌 총 인원 수" data-ph="예) 200명이면 200" data-x0="이 기관에 현재 배정된 인원 수" onclick="pick(this)">
      <div class="ico">👥</div><div class="nm">인력 배분</div><div class="ds">인력·정원을 나누는 문제</div>
    </div>
    <div class="tc" data-type="규제 권한" data-unit="점" data-hint="두 기관이 나눌 총 점수 (보통 100)" data-ph="예) 100" data-x0="이 기관이 현재 보유한 규제 권한 점수" onclick="pick(this)">
      <div class="ico">⚖️</div><div class="nm">규제 권한</div><div class="ds">규제·심의 권한을 나누는 문제</div>
    </div>
    <div class="tc" data-type="정책 우선순위" data-unit="점" data-hint="두 기관이 나눌 총 점수 (보통 100)" data-ph="예) 100" data-x0="이 기관의 현재 정책 우선순위 점수" onclick="pick(this)">
      <div class="ico">📋</div><div class="nm">정책 우선순위</div><div class="ds">정책 비중을 결정하는 문제</div>
    </div>
  </div>
</div>

<!-- 2. 총 자원 -->
<div class="card">
  <div class="card-title"><div class="sn">2</div><h2>두 기관이 나눌 자원의 총량은 얼마인가요?</h2></div>
  <div style="display:flex;align-items:center;gap:12px">
    <input type="number" id="tr" value="100" min="1" style="width:160px;border:2px solid #e5e7eb;border-radius:9px;padding:10px 14px;font-size:1.1rem;font-weight:700;outline:none" onfocus="this.style.borderColor='#3b82f6'" onblur="this.style.borderColor='#e5e7eb'">
    <span id="trUnit" style="font-size:1rem;font-weight:600;color:#6b7280">억 원</span>
  </div>
  <p class="desc" id="trHint" style="margin-top:8px;font-size:.82rem;color:#9ca3af">두 기관이 나눌 총 예산액</p>
</div>

<!-- 3. 두 기관 정보 -->
<div class="card">
  <div class="card-title"><div class="sn">3</div><h2>두 기관의 현황을 입력해 주세요</h2></div>
  <div class="two">
    <div class="inst ia">
      <h3>🔵 A 기관</h3>
      <div class="field">
        <label>기관 이름</label>
        <input type="text" id="an" value="A기관" placeholder="예: 기획재정부">
      </div>
      <div class="field">
        <label id="ax0L">현재 예산액은 얼마인가요?</label>
        <input type="number" id="ax0" value="50">
        <div class="desc" id="ax0D">이 기관이 현재 받고 있는 예산액</div>
      </div>
      <div class="field">
        <label>최소한 이것만큼은 받아야 합니다</label>
        <input type="number" id="aM" value="40">
        <div class="desc">이보다 적으면 공개적으로 받아들일 수 없는 마지노선</div>
      </div>
      <div class="sfield">
        <div class="lrow"><span class="lt">이 기관의 협상 영향력</span><span class="lv" id="awv">1.2</span></div>
        <input type="range" id="aw" min="0.5" max="3" step="0.1" value="1.2" oninput="uv('awv',this.value)">
        <div class="ep"><span>영향력 약함</span><span>영향력 강함</span></div>
      </div>
      <div class="sfield">
        <div class="lrow"><span class="lt">협상이 완전히 결렬되면 이 기관의 피해는?</span><span class="lv" id="adv">10</span></div>
        <input type="range" id="ad" min="0" max="50" step="1" value="10" oninput="uv('adv',this.value)">
        <div class="ep"><span>피해 거의 없음</span><span>피해 매우 큼</span></div>
      </div>
    </div>
    <div class="inst ib">
      <h3>🔴 B 기관</h3>
      <div class="field">
        <label>기관 이름</label>
        <input type="text" id="bn" value="B기관" placeholder="예: 과학기술부">
      </div>
      <div class="field">
        <label id="bx0L">현재 예산액은 얼마인가요?</label>
        <input type="number" id="bx0" value="50">
        <div class="desc" id="bx0D">이 기관이 현재 받고 있는 예산액</div>
      </div>
      <div class="field">
        <label>최소한 이것만큼은 받아야 합니다</label>
        <input type="number" id="bM" value="35">
        <div class="desc">이보다 적으면 공개적으로 받아들일 수 없는 마지노선</div>
      </div>
      <div class="sfield">
        <div class="lrow"><span class="lt">이 기관의 협상 영향력</span><span class="lv" id="bwv">1.0</span></div>
        <input type="range" id="bw" min="0.5" max="3" step="0.1" value="1.0" oninput="uv('bwv',this.value)">
        <div class="ep"><span>영향력 약함</span><span>영향력 강함</span></div>
      </div>
      <div class="sfield">
        <div class="lrow"><span class="lt">협상이 완전히 결렬되면 이 기관의 피해는?</span><span class="lv" id="bdv">8</span></div>
        <input type="range" id="bd" min="0" max="50" step="1" value="8" oninput="uv('bdv',this.value)">
        <div class="ep"><span>피해 거의 없음</span><span>피해 매우 큼</span></div>
      </div>
    </div>
  </div>
</div>

<!-- 4. 두 기관 관계 -->
<div class="card">
  <div class="card-title"><div class="sn">4</div><h2>두 기관은 평소 어떤 관계인가요?</h2></div>
  <div class="sfield">
    <div class="lrow"><span class="lt">두 기관 사이의 감정적 갈등 수준</span><span class="lv" id="hv">0.2</span></div>
    <input type="range" id="host" min="0" max="2" step="0.1" value="0.2" oninput="uv('hv',this.value)">
    <div class="ep"><span>😊 협력적·우호적</span><span>😤 극도로 적대적</span></div>
  </div>
</div>

<!-- 5. 협상 성향 (선택) -->
<details>
  <summary>더 정밀한 분석을 원하신다면 — 각 기관의 협상 성향 설정 <span style="font-size:.8rem;color:#9ca3af;font-weight:400">(선택사항)</span></summary>
  <div class="adv-body">
    <div class="adv-note">💡 아래 항목은 두 기관의 협상 성향을 잘 아실 때만 조정하세요. 기본값으로도 충분히 정확한 결과가 나옵니다.</div>
    <div class="bcols">
      <div class="bcol bca">
        <h4>🔵 A 기관의 협상 성향</h4>
        <div class="sfield"><div class="lrow"><span class="lt">손해 보는 것을 얼마나 두려워하나요?</span><span class="lv" id="allv">2.2</span></div><input type="range" id="all" min="0" max="5" step="0.1" value="2.2" oninput="uv('allv',this.value)"><div class="ep"><span>손해도 감수</span><span>손해를 극도로 싫어함</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">자기 기여도를 얼마나 과대평가하나요?</span><span class="lv" id="aalv">1.1</span></div><input type="range" id="aal" min="1" max="2" step="0.05" value="1.1" oninput="uv('aalv',this.value)"><div class="ep"><span>객관적으로 봄</span><span>매우 과대평가</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">상대방 이득을 내 손해로 보는 정도는?</span><span class="lv" id="aglv">0.3</span></div><input type="range" id="agl" min="0" max="1" step="0.05" value="0.3" oninput="uv('aglv',this.value)"><div class="ep"><span>협력 가능</span><span>상대 이득 = 내 손해</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">처음 요구한 것에 얼마나 집착하나요?</span><span class="lv" id="adlv">0.5</span></div><input type="range" id="adl" min="0" max="2" step="0.05" value="0.5" oninput="uv('adlv',this.value)"><div class="ep"><span>유연하게 조정</span><span>끝까지 고집</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">이겨도 불안해하거나 찝찝해하는 편인가요?</span><span class="lv" id="arlv">0.3</span></div><input type="range" id="arl" min="0" max="1" step="0.05" value="0.3" oninput="uv('arlv',this.value)"><div class="ep"><span>결과에 만족</span><span>이겨도 불안함</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">상대방이 더 받을 때 얼마나 불쾌해하나요?</span><span class="lv" id="ablv">0.5</span></div><input type="range" id="abl" min="0" max="2" step="0.05" value="0.5" oninput="uv('ablv',this.value)"><div class="ep"><span>개의치 않음</span><span>매우 불쾌해함</span></div></div>
      </div>
      <div class="bcol bcb">
        <h4>🔴 B 기관의 협상 성향</h4>
        <div class="sfield"><div class="lrow"><span class="lt">손해 보는 것을 얼마나 두려워하나요?</span><span class="lv" id="bllv">2.0</span></div><input type="range" id="bll" min="0" max="5" step="0.1" value="2.0" oninput="uv('bllv',this.value)"><div class="ep"><span>손해도 감수</span><span>손해를 극도로 싫어함</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">자기 기여도를 얼마나 과대평가하나요?</span><span class="lv" id="balv">1.1</span></div><input type="range" id="bal" min="1" max="2" step="0.05" value="1.1" oninput="uv('balv',this.value)"><div class="ep"><span>객관적으로 봄</span><span>매우 과대평가</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">상대방 이득을 내 손해로 보는 정도는?</span><span class="lv" id="bglv">0.4</span></div><input type="range" id="bgl" min="0" max="1" step="0.05" value="0.4" oninput="uv('bglv',this.value)"><div class="ep"><span>협력 가능</span><span>상대 이득 = 내 손해</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">처음 요구한 것에 얼마나 집착하나요?</span><span class="lv" id="bdlv">0.6</span></div><input type="range" id="bdl" min="0" max="2" step="0.05" value="0.6" oninput="uv('bdlv',this.value)"><div class="ep"><span>유연하게 조정</span><span>끝까지 고집</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">이겨도 불안해하거나 찝찝해하는 편인가요?</span><span class="lv" id="brlv">0.2</span></div><input type="range" id="brl" min="0" max="1" step="0.05" value="0.2" oninput="uv('brlv',this.value)"><div class="ep"><span>결과에 만족</span><span>이겨도 불안함</span></div></div>
        <div class="sfield"><div class="lrow"><span class="lt">상대방이 더 받을 때 얼마나 불쾌해하나요?</span><span class="lv" id="bblv">0.6</span></div><input type="range" id="bbl" min="0" max="2" step="0.05" value="0.6" oninput="uv('bblv',this.value)"><div class="ep"><span>개의치 않음</span><span>매우 불쾌해함</span></div></div>
      </div>
    </div>
  </div>
</details>

<!-- 실행 -->
<div class="run-wrap">
  <button class="run-btn" id="runBtn" onclick="run()">🔍 합의안 찾기</button>
</div>

<!-- 결과 -->
<div class="card" id="results">
  <div class="card-title"><div class="sn">✓</div><h2>분석 결과</h2></div>
  <div id="statusMsg"></div>
  <div class="bar-section">
    <div class="sec-label">최적 배분안</div>
    <div class="alloc-bar"><div class="aa" id="aa"></div><div class="ab" id="ab"></div></div>
    <div class="alloc-cards">
      <div class="ac aca"><div class="on" id="acaName">A 기관</div><div class="num" id="acaNum">—</div><div class="pct" id="acaPct"></div></div>
      <div class="ac acb"><div class="on" id="acbName">B 기관</div><div class="num" id="acbNum">—</div><div class="pct" id="acbPct"></div></div>
    </div>
  </div>
  <div class="util-row">
    <div class="uc uca"><div class="ul" id="ulaName">A 기관 수용 가능성</div><div class="us" id="usa">—</div><div class="ui" id="uia"></div></div>
    <div class="uc ucb"><div class="ul" id="ulbName">B 기관 수용 가능성</div><div class="us" id="usb">—</div><div class="ui" id="uib"></div></div>
  </div>
  <div class="note-box"><div class="nt">분석 해설</div><div class="nc" id="nc"></div></div>
</div>

</div>
<script>
let CT={type:'예산 배분',unit:'억 원',hint:'두 기관이 나눌 총 예산액',ph:'예) 100억이면 100',x0:'이 기관이 현재 받고 있는 예산액'};
function uv(id,v){document.getElementById(id).textContent=parseFloat(v).toFixed(parseFloat(v)<10?2:0)}
function pick(el){
  document.querySelectorAll('.tc').forEach(c=>c.classList.remove('on')); el.classList.add('on');
  CT={type:el.dataset.type,unit:el.dataset.unit,hint:el.dataset.hint,ph:el.dataset.ph,x0:el.dataset.x0};
  document.getElementById('trUnit').textContent=CT.unit;
  document.getElementById('trHint').textContent=CT.hint;
  const ql='현재 '+CT.unit+'은 얼마인가요?';
  document.getElementById('ax0L').textContent=ql; document.getElementById('bx0L').textContent=ql;
  document.getElementById('ax0D').textContent=CT.x0; document.getElementById('bx0D').textContent=CT.x0;
}
function g(id){return parseFloat(document.getElementById(id).value);}
function gs(id){return document.getElementById(id).value;}
function interp(s){return s>5?'✅ 적극 수용 가능':s>0?'🟡 조건부 수용 가능':'🔴 수용 어려움';}
async function run(){
  const btn=document.getElementById('runBtn'); btn.disabled=true; btn.textContent='🔄 분석 중...';
  const p={conflict_type:CT.type,total_resource:g('tr'),hostility_AB:g('host'),
    actor_A:{name:gs('an'),weight_w:g('aw'),disagreement_d:g('ad'),historical_x0:g('ax0'),min_reputation_M:g('aM'),bias_alpha:g('aal'),bias_lambda:g('all'),bias_gamma:g('agl'),bias_delta:g('adl'),bias_rho:g('arl'),bias_beta:g('abl')},
    actor_B:{name:gs('bn'),weight_w:g('bw'),disagreement_d:g('bd'),historical_x0:g('bx0'),min_reputation_M:g('bM'),bias_alpha:g('bal'),bias_lambda:g('bll'),bias_gamma:g('bgl'),bias_delta:g('bdl'),bias_rho:g('brl'),bias_beta:g('bbl')}};
  try{
    const r=await fetch('/api/v1/coordination/solve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
    show(await r.json(),p);
  }catch(e){alert('서버 연결 오류가 발생했습니다: '+e.message);}
  finally{btn.disabled=false; btn.textContent='🔍 합의안 찾기';}
}
function show(d,p){
  const el=document.getElementById('results'); el.style.display='block'; el.scrollIntoView({behavior:'smooth',block:'start'});
  const sc={success:{cls:'rs-ok',msg:'✅  양측이 받아들일 수 있는 합의안을 찾았습니다.'},infeasible:{cls:'rs-no',msg:'❌  양측의 최솟값 합이 총 자원을 초과합니다. 자원을 늘리거나 마지노선을 조정해 보세요.'},no_equilibrium:{cls:'rs-wn',msg:'⚠️  이 자원만으로는 합의점을 찾기 어렵습니다. 다른 조건(자원·권한 등)을 함께 묶어 협상하는 방법을 권장합니다.'}};
  const s=sc[d.status]||sc.success;
  document.getElementById('statusMsg').innerHTML=`<div class="rst ${s.cls}">${s.msg}</div>`;
  const tot=p.total_resource, aS=d.optimized_allocation.actor_A_share, bS=d.optimized_allocation.actor_B_share;
  const aN=p.actor_A.name, bN=p.actor_B.name, u=CT.unit;
  const aP=(aS/tot*100).toFixed(1), bP=(bS/tot*100).toFixed(1);
  document.getElementById('aa').style.width=aP+'%'; document.getElementById('aa').textContent=aP>12?aN:'';
  document.getElementById('ab').style.width=bP+'%'; document.getElementById('ab').textContent=bP>12?bN:'';
  document.getElementById('acaName').textContent=aN; document.getElementById('acaNum').textContent=aS+' '+u; document.getElementById('acaPct').textContent='전체의 '+aP+'%';
  document.getElementById('acbName').textContent=bN; document.getElementById('acbNum').textContent=bS+' '+u; document.getElementById('acbPct').textContent='전체의 '+bP+'%';
  const uA=d.psychological_satisfaction.actor_A_utility, uB=d.psychological_satisfaction.actor_B_utility;
  document.getElementById('ulaName').textContent=aN+' 수용 가능성'; document.getElementById('usa').textContent=uA; document.getElementById('uia').textContent=interp(uA);
  document.getElementById('ulbName').textContent=bN+' 수용 가능성'; document.getElementById('usb').textContent=uB; document.getElementById('uib').textContent=interp(uB);
  document.getElementById('nc').textContent=d.coordination_note;
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
