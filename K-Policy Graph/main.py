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

    # 6. 반응적 가치하락 → hostility_AB 로 상위 모델에서 처리
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
## 📖 사용 설명서

### 이 엔진이 하는 일
부처·기관 간 어떤 종류의 의견 불일치든, **갈등의 핵심 자원을 수치로 표현**할 수 있으면
심리적 편향 7종을 반영한 내시 바게닝으로 **양측이 심리적으로 수용 가능한 최적 조정안**을 산출합니다.

---

### 적용 가능한 갈등 유형

| 갈등 유형 | `conflict_type` 입력값 | `total_resource` 기준 | `historical_x0` 기준 |
|-----------|----------------------|----------------------|----------------------|
| 예산·재원 배분 | `"예산 배분"` | 총 예산(억 원) | 전년도 배분액 |
| 사업 관할권 | `"사업 관할권"` | 100점 척도 | 현재 점유 비중 |
| 인력·정원 배분 | `"인력 배분"` | 총 정원(명) | 현재 인원 |
| 규제·심의 권한 | `"규제 권한"` | 100점 척도 | 현재 권한 점수 |
| 정책 우선순위 | `"정책 우선순위"` | 100점 척도 | 기존 우선순위 점수 |

---

### 사용 방법

1. 아래 **`POST /api/v1/coordination/solve`** 항목을 클릭합니다.
2. **"Try it out"** 버튼을 클릭합니다.
3. 요청 본문(JSON)에 갈등 유형과 두 행위자의 정보를 입력합니다.
4. **"Execute"** 버튼을 클릭합니다.
5. 하단 **응답(Response)** 에서 조정 결과를 확인합니다.

---

### 입력 파라미터

**갈등 설정**

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `conflict_type` | 갈등 유형 (결과 해설에 반영) | `"사업 관할권"` |
| `total_resource` | 협상 대상 자원의 총량 | `100` |
| `hostility_AB` | 두 행위자 간 대립도 H (0=중립) | `0.3` |

**행위자 기본 정보**

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `name` | 행위자 명칭 | `"환경부"` |
| `weight_w` | 협상 권한 가중치 (AHP 점수 등) | `1.2` |
| `disagreement_d` | 협상 결렬 시 감수할 손실 수치 | `10` |
| `historical_x0` | 준거점 (현재 점유량·기존 배분량) | `60` |
| `min_reputation_M` | 공개적으로 수용 가능한 최소값 (체면 마지노선) | `45` |

**심리 편향 7종 계수**

| 파라미터 | 편향 | 의미 | 기본값 |
|----------|------|------|--------|
| `bias_alpha` | ① 자기고양 | 자기 몫을 과대 인식할수록 높게 | `1.1` |
| `bias_lambda` | ② 부존 효과·매몰비용 | 준거점 이하 손실에 민감할수록 높게 | `2.2` |
| `bias_gamma` | ③ 고정된 파이 편향 | 상대방 이득을 내 손실로 볼수록 높게 | `0.3` |
| `bias_delta` | ④ 앵커링 효과 | 첫 요구안에 집착할수록 높게 | `0.5` |
| `anchor_demand` | ④ 앵커 기준값 | 첫 요구안 수치 (미입력 시 준거점×1.5 자동 적용) | `null` |
| `bias_rho` | ⑤ 후회 회피 | 너무 많이 얻는 것도 불안할수록 높게 | `0.3` |

*(편향⑥ 반응적 가치하락은 `hostility_AB`로, 편향⑦ 체면은 `min_reputation_M`으로 설정)*

---

### 결과 해석

| 응답 필드 | 설명 |
|-----------|------|
| `status` | 조정 성공 여부 |
| `optimized_allocation.actor_A_share` | A측 최적 배분량 (입력 단위와 동일) |
| `optimized_allocation.actor_B_share` | B측 최적 배분량 (입력 단위와 동일) |
| `psychological_satisfaction.actor_A_utility` | A측 심리적 수용도 (높을수록 만족) |
| `psychological_satisfaction.actor_B_utility` | B측 심리적 수용도 (높을수록 만족) |
| `coordination_note` | 갈등 유형과 주요 편향을 반영한 자연어 해설 |

---

### 상태 코드 의미

- **`success`** : 양측이 심리적으로 수용 가능한 최적 조정안 도출
- **`infeasible`** : 양측 체면 마지노선 합이 총 자원을 초과 → 추가 자원 확보 또는 패키지 딜 필요
- **`no_equilibrium`** : 단일 자원 조정만으로 내시균형 불가 → 연관 자원을 묶은 2단계 중재 권장
"""

app = FastAPI(
    title="Project HARMONIA — 다부처 갈등 조정 엔진",
    description=사용설명서,
    version="1.0.0",
    openapi_tags=태그_메타데이터,
)


@app.get(
    "/",
    tags=["시스템"],
    summary="서버 상태 확인",
    description="서버가 정상 실행 중인지 확인합니다.",
)
def root() -> dict:
    return {
        "프로젝트": "HARMONIA / NASIS",
        "조정_엔드포인트": "POST /api/v1/coordination/solve",
        "사용설명서": "/docs",
    }


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
