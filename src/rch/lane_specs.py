from __future__ import annotations

from collections import OrderedDict
from typing import Any


LaneSpec = dict[str, Any]


LANE_SPECS: "OrderedDict[str, LaneSpec]" = OrderedDict(
    [
        (
            "intake",
            {
                "title": "입력 정리·개인정보 점검",
                "purpose": "아이디어, 대회 규격, 레퍼런스, 수업사진, 설문결과, 활동지, 산출물을 안전하게 분류한다.",
                "inputs": [
                    "input/ideas/",
                    "input/rules/",
                    "input/references/",
                    "input/evidence/",
                    "input/photos/",
                    "input/surveys/",
                ],
                "process": [
                    "자료를 report fact, student evidence, visual evidence, reference pattern, appendix candidate로 나눈다.",
                    "학생 이름, 얼굴, 학번, 연락처, 학교 외부 공개 위험을 표시한다.",
                    "확정 사실과 작성자 추정, 아이디어, 빈칸을 분리한다.",
                    "최종 보고서에 바로 넣을 수 없는 자료는 placeholder 또는 forbidden으로 표시한다.",
                ],
                "outputs": [
                    "input-inventory 표",
                    "privacy-risk 표",
                    "missing-input 질문 0~5개",
                    "claim-ledger.json",
                ],
                "guardrails": [
                    "사진은 설명 가능성보다 개인정보 위험을 먼저 본다.",
                    "설문 숫자는 원자료·계산식 없으면 real로 두지 않는다.",
                ],
            },
        ),
        (
            "brainstorm",
            {
                "title": "보고서 아이디어·연구 프레임",
                "purpose": "대회 심사 기준에 맞는 제목, 연구 질문, 연구 모형, 실천과제 구조를 만든다.",
                "inputs": ["input/ideas/", "input/rules/", "input/evidence/"],
                "process": [
                    "알파벳 약어와 한글 스토리를 함께 만든다.",
                    "주제축과 실행단계축을 분리해 이중 프레임 가능성을 검토한다.",
                    "실천과제는 3~5개로 제한하고, 결과·확산까지 이어지게 설계한다.",
                    "첫 3분 안에 필요성, 수업 구조, 학생 변화가 읽히는지 점검한다.",
                ],
                "outputs": [
                    "제목 후보 5개",
                    "수업 모형 1~3개",
                    "실천과제 구조",
                    "심사 기준 대응표",
                ],
                "guardrails": [
                    "멋진 이름보다 증거로 설명 가능한 구조를 우선한다.",
                    "교사·학생 실천으로 확인되지 않는 성과는 claim으로 쓰지 않는다.",
                ],
            },
        ),
        (
            "reference-miner",
            {
                "title": "레퍼런스 보고서 구조 추출",
                "purpose": "우수 보고서와 대회 양식에서 문장을 베끼지 않고 목차, 표, 결과 제시, 부록 패턴과 이론적 배경 참고자료를 추출한다.",
                "inputs": ["input/references/", "input/research/", "input/rules/"],
                "process": [
                    "대회 양식의 장·절 구조와 I 시작 - II 준비 - III 설계 - IV 실행/결과 - V 결론/제언 구조를 함께 확인한다.",
                    "실천과제 수, 표 밀도, 그림/아이콘 위치, 부록 구성, 결과 장 흐름을 뽑는다.",
                    "`rch research-background` 결과의 배경지식·선행연구는 보고서 이론적 배경에 연결하되 원문 표현은 베끼지 않는다.",
                    "설문 결과를 평균, p값, 효과크기, 질적 인용으로 묶는 방식을 기록한다.",
                    "좋은 보고서의 장치만 추출하고 문장 표현은 새로 쓴다.",
                ],
                "outputs": [
                    "reference-pattern 표",
                    "recommended-outline",
                    "table-pattern inventory",
                    "appendix-pattern inventory",
                ],
                "guardrails": [
                    "레퍼런스 문장·캡션·표 내용을 복사하지 않는다.",
                    "확인 불가한 PDF 추출 내용은 확인불가로 표시한다.",
                ],
            },
        ),
        (
            "evidence-curator",
            {
                "title": "증거 ledger·주장 안전화",
                "purpose": "보고서 주장과 실제 증거를 연결해 허위·과장·미확정 주장을 막는다.",
                "inputs": ["input/evidence/", "input/surveys/", "input/photos/"],
                "process": [
                    "각 증거에 id, 경로, 날짜, 수업 장면, 사용 가능 범위를 붙인다.",
                    "주장을 real, derived, placeholder, forbidden으로 분류한다.",
                    "derived claim은 계산식이나 도출 과정을 적는다.",
                    "미확정 확산 실적, 학생 발화, 수치, 사진 설명은 placeholder로 둔다.",
                ],
                "outputs": [
                    "evidence-index",
                    "claim-ledger.json",
                    "unsafe-claims 표",
                    "human-confirmation 질문",
                ],
                "guardrails": [
                    "증거 없는 학생 반응·설문 수치·성과를 만들지 않는다.",
                    "final 후보에는 real/derived만 보낸다.",
                ],
            },
        ),
        (
            "survey-analyzer",
            {
                "title": "설문결과 분석",
                "purpose": "사전·사후 설문과 자유응답을 보고서에 넣을 수 있는 표와 해석으로 바꾼다.",
                "inputs": ["input/surveys/"],
                "process": [
                    "원자료, 표본 수, 문항, 척도, 결측값을 먼저 기록한다.",
                    "사전·사후 평균, 평균차, 가능하면 효과크기와 p값을 계산하되 소표본 한계를 명시한다.",
                    "정량 결과와 자유응답 인용을 연결한다.",
                    "유의하지 않은 결과도 정직하게 쓰고, 과장 해석을 금지한다.",
                ],
                "outputs": [
                    "survey-summary 표",
                    "result-interpretation 초안",
                    "quote-candidates",
                    "claim-ledger.json",
                ],
                "guardrails": [
                    "원자료 없는 숫자는 real claim이 아니다.",
                    "학생 자유응답은 익명화 후 사용한다.",
                ],
            },
        ),
        (
            "photo-curator",
            {
                "title": "수업사진·시각 증거 큐레이션",
                "purpose": "수업사진과 활동 장면을 개인정보 안전성과 보고서 설득력 기준으로 고른다.",
                "inputs": ["input/photos/", "input/evidence/"],
                "process": [
                    "사진마다 장면, 수업 단계, 보여주는 학생 행동, 개인정보 위험을 표로 적는다.",
                    "얼굴·이름·학번·개인 화면이 보이면 익명화 필요로 표시한다.",
                    "보고서 본문용, 요약서용, 부록용, 제외용으로 나눈다.",
                    "사진 설명은 관찰 가능한 행동만 쓴다.",
                ],
                "outputs": [
                    "photo-manifest",
                    "visual-placement plan",
                    "privacy-action list",
                    "claim-ledger.json",
                ],
                "guardrails": [
                    "사진으로 확인되지 않는 수업 효과를 설명하지 않는다.",
                    "학생 개인정보가 남은 이미지는 final 후보에 넣지 않는다.",
                ],
            },
        ),
        (
            "draft-writer",
            {
                "title": "보고서 본문 초안",
                "purpose": "자료와 lane 결과를 바탕으로 최종 진술형 보고서 본문을 쓴다.",
                "inputs": ["lanes/*/*/lane-output.md", "input/rules/", "input/research/"],
                "process": [
                    "I~V장 흐름으로 필요성, 준비, 설계, 실행, 결과, 제언을 연결한다.",
                    "이론적 배경과 선행연구는 `input/research/background-research.json`의 출처를 확인해 표로 요약한다.",
                    "표가 말하고 본문이 해석하는 구조로 쓴다.",
                    "각 문단의 핵심 claim을 claim-ledger와 맞춘다.",
                    "AI 티가 나는 대구, 과도한 강조, 빈 수식어, 반복 키워드를 줄인다.",
                ],
                "outputs": [
                    "report body markdown",
                    "section claim map",
                    "remaining-risk list",
                    "claim-ledger.json",
                ],
                "guardrails": [
                    "본문에는 예정, 추후, 초안, 미정, TODO를 쓰지 않는다.",
                    "확정되지 않은 내용은 TODO가 아니라 claim-ledger placeholder로 둔다.",
                ],
            },
        ),
        (
            "table-layout",
            {
                "title": "표 중심 편집 설계",
                "purpose": "대회별 보고서 양식 안에서 심사자가 빠르게 읽을 수 있게 표, 카드, 문단 밀도를 설계한다.",
                "inputs": ["lanes/draft-writer/", "lanes/reference-miner/"],
                "process": [
                    "긴 설명은 3~5열 표나 단계 카드로 바꾸되, 표가 페이지 하단에서 잘리지 않게 한다.",
                    "표 바로 뒤 본문이 끊기지 않도록 해석 문단을 붙인다.",
                    "표 제목, 캡션, 번호, 그림 배치 규칙을 통일한다.",
                    "대회 규정의 분량 제한을 전제로 표 폭, 행 수, 문장 길이를 보수적으로 잡는다.",
                ],
                "outputs": [
                    "table-map",
                    "page-flow plan",
                    "caption list",
                    "compression targets",
                ],
                "guardrails": [
                    "표를 늘려 독해를 방해하지 않는다.",
                    "표/그림 분할, orphan heading, 하단 잘림을 finalizer에 넘기지 않는다.",
                ],
            },
        ),
        (
            "summary-sheet",
            {
                "title": "요약서",
                "purpose": "한눈에 연구 주제, 수업모형, 실천, 결과, 확산을 보여주는 요약서를 만든다.",
                "inputs": ["lanes/brainstorm/", "lanes/draft-writer/", "lanes/table-layout/"],
                "process": [
                    "제목, 한 줄 문제의식, 수업 모형, 실천과제, 핵심 결과, 일반화 가능성을 압축한다.",
                    "표와 아이콘 중심으로 구성하고 장문 설명을 피한다.",
                    "보고서 본문 claim과 충돌하지 않게 claim-ledger를 대조한다.",
                ],
                "outputs": [
                    "summary sheet markdown",
                    "visual hierarchy plan",
                    "claim-ledger.json",
                ],
                "guardrails": [
                    "요약서에 본문보다 센 주장을 쓰지 않는다.",
                    "근거 없는 수치와 사진 설명을 넣지 않는다.",
                ],
            },
        ),
        (
            "toc-builder",
            {
                "title": "목차·페이지 계획",
                "purpose": "I~V장 목차와 인쇄 페이지 기준 페이지 번호를 관리한다.",
                "inputs": ["lanes/draft-writer/", "lanes/table-layout/"],
                "process": [
                    "표지, 요약, 목차 등 앞쪽 면수와 본문 인쇄 페이지 기준을 분리한다.",
                    "장/절 제목을 보고서 전체 용어와 맞춘다.",
                    "페이지 변화가 생기면 목차 번호를 다시 맞추도록 finalizer에게 명확히 넘긴다.",
                ],
                "outputs": [
                    "toc markdown",
                    "page-numbering assumptions",
                    "heading consistency report",
                ],
                "guardrails": [
                    "확인하지 않은 페이지 번호를 확정값처럼 쓰지 않는다.",
                    "목차와 본문 제목이 다르면 final 후보로 보내지 않는다.",
                ],
            },
        ),
        (
            "appendix-builder",
            {
                "title": "부록 구성",
                "purpose": "교수학습 과정안, 루브릭, 활동지, 설문지, 사진/산출물 증거를 부록으로 구성한다.",
                "inputs": ["input/evidence/", "input/photos/", "input/surveys/", "lanes/table-layout/"],
                "process": [
                    "본문을 보강하는 부록만 남기고 중복 자료는 제외한다.",
                    "과정안 1~2개, 루브릭, 활동지, 설문 문항, 대표 산출물 순으로 묶는다.",
                    "학생 식별 정보와 원자료 민감 정보는 익명화 목록에 올린다.",
                ],
                "outputs": [
                    "appendix markdown",
                    "appendix manifest",
                    "privacy checklist",
                ],
                "guardrails": [
                    "학생 개인정보가 남은 원자료를 부록에 넣지 않는다.",
                    "본문 claim을 증명하지 못하는 장식성 부록을 줄인다.",
                ],
            },
        ),
        (
            "icon-visual",
            {
                "title": "아이콘·도식·시각 언어",
                "purpose": "수업 모형, 단계, 결과를 일관된 아이콘과 도식으로 정리한다.",
                "inputs": ["lanes/brainstorm/", "lanes/table-layout/", "input/assets/"],
                "process": [
                    "수업 단계마다 같은 크기·톤의 아이콘을 배정한다.",
                    "아이콘은 정보 구조를 돕는 곳에만 쓰고 장식으로 남발하지 않는다.",
                    "요약서와 본문 표의 시각 언어를 맞춘다.",
                ],
                "outputs": [
                    "visual-asset manifest",
                    "icon-placement table",
                    "figure-caption list",
                ],
                "guardrails": [
                    "저작권 불명 이미지나 학생 식별 이미지를 쓰지 않는다.",
                    "어두운 장식보다 실제 수업/도구/결과를 보여준다.",
                ],
            },
        ),
        (
            "critic",
            {
                "title": "심사자 관점 비평",
                "purpose": "심사표, 형식, 독해 흐름, 허위 주장, 개인정보, AI 티를 공격적으로 점검한다.",
                "inputs": ["lanes/*/*/lane-output.md", "input/rules/"],
                "process": [
                    "첫 3분 독해, 심사기준 대응, 표 흐름, 결과 설득력, 개인정보를 따로 본다.",
                    "문제는 위치, 이유, 수정 지시로 쓴다.",
                    "자동 수정 가능 항목과 사용자 확인 필요 항목을 분리한다.",
                ],
                "outputs": [
                    "review table",
                    "blocking issues",
                    "machine feedback json",
                    "rubric-score.json",
                    "claim-ledger.json",
                ],
                "required_files": ["rubric-score.json"],
                "guardrails": [
                    "좋아 보인다는 평보다 고칠 수 있는 지시를 쓴다.",
                    "사실 확인이 필요한 항목을 임의로 확정하지 않는다.",
                ],
            },
        ),
        (
            "finalizer",
            {
                "title": "최종 조립·검증",
                "purpose": "본문, 요약서, 목차, 부록을 하나의 최종 후보로 묶고 HWPX 전 검증 체크리스트를 만든다.",
                "inputs": ["lanes/*/*/lane-output.md", "output/"],
                "process": [
                    "보고서 본문, 요약서, 목차, 부록이 서로 같은 claim을 쓰는지 확인한다.",
                    "final forbidden 문구와 placeholder claim을 제거한다.",
                    "HWPX 조립은 한 주체만 수행하고, 렌더 후 페이지/표/목차를 재검수한다.",
                    "HOP/Hancom 기준 페이지 수와 렌더 품질을 최종 판정 기준으로 둔다.",
                ],
                "outputs": [
                    "finalization checklist",
                    "HWPX assembly plan",
                    "render QA matrix",
                    "remaining-risk list",
                ],
                "guardrails": [
                    "여러 에이전트가 같은 HWPX를 동시에 수정하지 않는다.",
                    "render 전 통과와 Hancom 실제 표시를 혼동하지 않는다.",
                ],
            },
        ),
    ]
)


FINAL_BUNDLE_FILES = (
    "report-draft.md",
    "summary-sheet.md",
    "toc.md",
    "appendix.md",
    "finalization-checklist.md",
)


def render_lane_input(lane: str, agent: str) -> str:
    spec = LANE_SPECS[lane]
    return "\n".join(
        [
            f"# {spec['title']}",
            "",
            f"lane: {lane}",
            f"agent: {agent}",
            "",
            "## 목적",
            "",
            spec["purpose"],
            "",
            "## 입력 위치",
            "",
            *[f"- `{item}`" for item in spec["inputs"]],
            "",
            "## 작업 절차",
            "",
            *[f"{index}. {item}" for index, item in enumerate(spec["process"], 1)],
            "",
            "## 필수 산출물",
            "",
            "- `lane-output.md`",
            "- `lane-output.json`",
            "- `claim-ledger.json`",
            "- `verdict.json`",
            *[f"- `{item}`" for item in spec.get("required_files", [])],
            "- `evidence/`",
            "",
            "## lane-output.md에 포함할 내용",
            "",
            *[f"- {item}" for item in spec["outputs"]],
            "",
            "## 절대 금지",
            "",
            *[f"- {item}" for item in spec["guardrails"]],
            "- 레퍼런스 보고서 문장 복사 금지. 구조와 패턴만 추출.",
            "- 학생 자료, 사진, 설문 원자료는 익명화 전 final 후보 반영 금지.",
            "- 불확실한 내용은 `placeholder`, 쓰면 안 되는 내용은 `forbidden` claim으로 표시.",
            "",
            "## claim-ledger 규칙",
            "",
            "- `real`: 실제 증빙으로 직접 확인.",
            "- `derived`: 실제 증빙에서 계산/도출했고 방법 기록.",
            "- `placeholder`: draft에서만 사용. final 반영 금지.",
            "- `forbidden`: 보고서 반영 금지.",
            "",
        ]
    )
