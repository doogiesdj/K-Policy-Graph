"""
Project HARMONIA (NASIS)
다부처 갈등 조정 — 심리적 수정 내시 바게닝(Nash Bargaining) 프로토타입

행동게임이론의 심리적 편향(손실회피·시기심·자기고양·체면)을 정량화하여
내시 바게닝 목적함수에 반영하고, 양측 부처의 심리적 저항을 최소화하는
최적 자원 배분(x_A*, x_B*)을 도출한다.

Tech Stack: Python 3.10+ / FastAPI / Pydantic / SciPy

실행:
    pip install fastapi uvicorn scipy pydantic
    uvicorn main:app --reload
    # http://127.0.0.1:8000/docs 에서 /api/v1/coordination/solve 테스트

단독 실행(서버 없이 데모):
    python main.py
"""

from __future__ import annotations

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
    """행위자 레이어 + 심리 프로파일 레이어를 하나로 묶은 입력 모델."""

    name: str = Field(..., description="부처 명칭")
    weight_w: float = Field(..., gt=0, description="국정과제 권한 가중치 w_i (AHP 연동)")
    disagreement_d: float = Field(..., description="결렬점 d_i (협상 결렬 시 타격 수치)")
    historical_x0: float = Field(..., description="준거점 예산 x_0 (손실회피 기준점)")

    # --- 심리 편향 계수 ---
    bias_lambda: float = Field(2.2, ge=0, description="손실 회피 계수 λ_i (기본 2.2)")
    bias_beta: float = Field(0.5, ge=0, description="불평등 혐오/시기심 계수 β_i")
    bias_alpha: float = Field(1.1, ge=1.0, description="자기고양 편향 가중치 α_i (≥1)")
    min_reputation_M: float = Field(..., ge=0, description="최소 체면 마지노선 M_i")


class CoordinationRequest(BaseModel):
    total_budget: float = Field(..., gt=0, description="총 예산 제약 B")
    actor_A: Actor
    actor_B: Actor
    hostility_AB: float = Field(
        0.0, ge=0, description="부처 간 대립도 H_ij (반응적 가치하락 지수)"
    )


class Allocation(BaseModel):
    actor_A_budget: float
    actor_B_budget: float


class Satisfaction(BaseModel):
    actor_A_utility: float
    actor_B_utility: float


class CoordinationResponse(BaseModel):
    status: str
    optimized_allocation: Allocation
    psychological_satisfaction: Satisfaction
    coordination_note: str


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
    """체면 페널티 (청중 효과·평판 위험): x_i < M_i 이면 ∞(대용 상수), 아니면 0."""
    return REPUTATION_INF_PENALTY if x_i < m_i else 0.0


def modified_utility(
    x_i: float, x_j: float, actor: Actor, hostility: float
) -> float:
    """부처 i의 수정 효용 V_i(x_i, x_j)."""
    return (
        base_utility(x_i, actor.bias_alpha)
        - loss_penalty(x_i, actor.historical_x0, actor.bias_lambda)
        - envy_penalty(x_i, x_j, actor.bias_beta, hostility)
        - reputation_penalty(x_i, actor.min_reputation_M)
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
    x_B = req.total_budget - x_A

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
    budget = req.total_budget

    # 탐색 구간: x_A ∈ [M_A, B - M_B]  (양측 체면 마지노선 보장)
    lower = A.min_reputation_M
    upper = budget - B.min_reputation_M

    if lower > upper:
        return CoordinationResponse(
            status="infeasible",
            optimized_allocation=Allocation(actor_A_budget=0.0, actor_B_budget=0.0),
            psychological_satisfaction=Satisfaction(
                actor_A_utility=0.0, actor_B_utility=0.0
            ),
            coordination_note=(
                f"체면 마지노선 합({A.min_reputation_M}+{B.min_reputation_M})이 "
                f"총 예산({budget})을 초과하여 실행 가능한 조정안이 없습니다. "
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
                actor_A_budget=round(x_A, 2), actor_B_budget=round(x_B, 2)
            ),
            psychological_satisfaction=Satisfaction(
                actor_A_utility=0.0, actor_B_utility=0.0
            ),
            coordination_note=(
                "단일 예산 조정만으로는 양측 결렬점을 동시에 만족하는 "
                "내시균형이 도출되지 않았습니다. 패키지 딜(로그롤링)로 "
                "온톨로지상 연관 자원(규제 권한 등)을 리워드로 결합하는 "
                "2단계 중재를 권장합니다."
            ),
        )

    V_A = modified_utility(x_A, x_B, A, req.hostility_AB)
    V_B = modified_utility(x_B, x_A, B, req.hostility_AB)

    return CoordinationResponse(
        status="success",
        optimized_allocation=Allocation(
            actor_A_budget=round(x_A, 2), actor_B_budget=round(x_B, 2)
        ),
        psychological_satisfaction=Satisfaction(
            actor_A_utility=round(V_A, 2), actor_B_utility=round(V_B, 2)
        ),
        coordination_note=_build_note(req, x_A, x_B),
    )


def _build_note(req: CoordinationRequest, x_A: float, x_B: float) -> str:
    """조정 결과에 대한 자연어 해설 생성."""
    A, B = req.actor_A, req.actor_B
    parts: list[str] = []

    # 준거점 대비 증감
    for actor, x in ((A, x_A), (B, x_B)):
        delta = x - actor.historical_x0
        if abs(delta) < 0.5:
            trend = f"준거점({actor.historical_x0:.0f}) 수준 유지"
        elif delta > 0:
            trend = f"준거점({actor.historical_x0:.0f}) 대비 +{delta:.1f} 증액"
        else:
            trend = f"준거점({actor.historical_x0:.0f}) 대비 {delta:.1f} 감액"
        parts.append(f"{actor.name}: {x:.1f} ({trend})")

    # 손실회피·체면 요인 강조
    high_lambda = max((A, B), key=lambda a: a.bias_lambda)
    note = (
        " / ".join(parts)
        + f". {high_lambda.name}의 높은 손실회피 성향(λ={high_lambda.bias_lambda})과 "
        f"체면 마지노선(M={high_lambda.min_reputation_M:.0f})을 반영해 "
        "심리적 저항을 최소화하는 방향으로 조정되었습니다."
    )
    if req.hostility_AB > 0:
        note += f" 부처 간 대립도(H={req.hostility_AB})로 인한 반응적 가치하락도 가중 반영되었습니다."
    return note


# ---------------------------------------------------------------------------
# Module 4: FastAPI 인터페이스
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Project HARMONIA — 다부처 갈등 조정 엔진",
    description="심리적 수정 내시 바게닝 기반 국무조정 알고리즘 프로토타입",
    version="1.0.0",
)


@app.get("/")
def root() -> dict:
    return {
        "project": "HARMONIA / NASIS",
        "endpoint": "POST /api/v1/coordination/solve",
        "docs": "/docs",
    }


@app.post("/api/v1/coordination/solve", response_model=CoordinationResponse)
def solve(req: CoordinationRequest) -> CoordinationResponse:
    """두 부처의 데이터와 심리 파라미터를 입력받아 최적 내시 조정값을 계산한다."""
    return solve_coordination(req)


# ---------------------------------------------------------------------------
# 단독 실행 데모 (서버 없이 솔버 직접 호출)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    demo = CoordinationRequest(
        total_budget=100,
        actor_A=Actor(
            name="A부처",
            weight_w=1.2,
            disagreement_d=10,
            historical_x0=50,
            bias_lambda=2.2,
            bias_beta=0.5,
            bias_alpha=1.1,
            min_reputation_M=40,
        ),
        actor_B=Actor(
            name="B부처",
            weight_w=1.0,
            disagreement_d=8,
            historical_x0=50,
            bias_lambda=2.0,
            bias_beta=0.6,
            bias_alpha=1.1,
            min_reputation_M=35,
        ),
        hostility_AB=0.2,
    )
    res = solve_coordination(demo)
    print(json.dumps(res.model_dump(), ensure_ascii=False, indent=2))
