#!/usr/bin/env python3
"""Scrape CVPR 2026 Open Access papers and create one Korean markdown summary per paper.

Requirements:
- stdlib Python 3.10+
- pdftotext command available on PATH
- codex CLI authenticated locally for --summarize

Examples:
  python cvpr2026_summarize.py --scrape
  python cvpr2026_summarize.py --summarize --limit 3
  python cvpr2026_summarize.py --summarize --all
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = "https://openaccess.thecvf.com"
LIST_URL = "https://openaccess.thecvf.com/CVPR2026?day=all"
DEFAULT_CODEX_MODEL = os.environ.get("CODEX_MODEL")
DEFAULT_CODEX_COMMAND = os.environ.get("CODEX_CLI")
DEFAULT_CATEGORIES_PATH = Path("data/cvpr2026_categories.json")
DEFAULT_ZOTERO_DIR = Path("data/zotero")
WINDOWS_PDFTOTEXT_CANDIDATES = [
    Path(r"C:\Program Files\Git\mingw64\bin\pdftotext.exe"),
    Path(r"C:\Program Files\Git\usr\bin\pdftotext.exe"),
]

# Official CVPR 2026 Call for Papers topic list.
# Source: https://cvpr.thecvf.com/Conferences/2026/CallForPapers
CVPR2026_CATEGORIES = [
    "3D from multi-view and sensors",
    "3D from single images",
    "Adversarial attack and defense",
    "Autonomous driving",
    "Biometrics",
    "Computational imaging",
    "Computer vision for social good",
    "Computer vision theory",
    "Datasets and evaluation",
    "Deep learning architectures and techniques",
    "Document analysis and understanding",
    "Efficient and scalable vision",
    "Embodied vision: Active agents, simulation",
    "Event-based cameras",
    "Explainable computer vision",
    "Humans: Face, body, pose, gesture, movement",
    "Image and video synthesis and generation",
    "Low-level vision",
    "Machine learning (other than deep learning)",
    "Medical and biological vision, cell microscopy",
    "Multimodal learning",
    "Optimization methods (other than deep learning)",
    "Photogrammetry and remote sensing",
    "Physics-based vision and shape-from-X",
    "Recognition: Categorization, detection, retrieval",
    "Representation learning",
    "Computer Vision for Robotics",
    "Scene analysis and understanding",
    "Segmentation, grouping and shape analysis",
    "Self-, semi-, meta- and unsupervised learning",
    "Transfer/ low-shot/ continual/ long-tail learning",
    "Transparency, fairness, accountability, privacy and ethics in vision",
    "Video: Action and event understanding",
    "Video: Low-level analysis, motion, and tracking",
    "Vision + graphics",
    "Vision, language, and reasoning",
    "Vision applications and systems",
]

CATEGORY_ALIASES = {category.casefold(): category for category in CVPR2026_CATEGORIES}

CATEGORY_KEYWORDS = {
    "3D from multi-view and sensors": ["multi-view", "multiview", "lidar", "point cloud", "sensor", "depth", "stereo"],
    "3D from single images": ["monocular", "single image", "single-view", "single view", "depth estimation"],
    "Adversarial attack and defense": ["adversarial", "attack", "defense", "robustness"],
    "Autonomous driving": ["autonomous driving", "driving", "vehicle", "traffic", "nuScenes", "waymo"],
    "Biometrics": ["biometric", "face recognition", "fingerprint", "iris", "gait"],
    "Computational imaging": ["computational imaging", "camera", "sensor", "isp", "coded aperture"],
    "Computer vision for social good": ["social good", "sustainability", "disaster", "accessibility"],
    "Computer vision theory": ["theory", "generalization bound", "identifiability"],
    "Datasets and evaluation": ["dataset", "benchmark", "evaluation", "metric"],
    "Deep learning architectures and techniques": ["architecture", "transformer", "network", "diffusion", "backbone"],
    "Document analysis and understanding": ["document", "ocr", "table recognition", "layout"],
    "Efficient and scalable vision": ["efficient", "scalable", "compression", "pruning", "quantization", "latency"],
    "Embodied vision: Active agents, simulation": ["embodied", "agent", "simulation", "navigation", "active"],
    "Event-based cameras": ["event camera", "event-based", "neuromorphic"],
    "Explainable computer vision": ["explainable", "interpretability", "explanation"],
    "Humans: Face, body, pose, gesture, movement": ["human", "pose", "gesture", "body", "face", "motion"],
    "Image and video synthesis and generation": ["generation", "synthesis", "generative", "diffusion", "editing", "text-to-image", "text-to-video"],
    "Low-level vision": ["super-resolution", "denoising", "deblurring", "restoration", "enhancement", "low-light"],
    "Machine learning (other than deep learning)": ["bayesian", "kernel", "graphical model"],
    "Medical and biological vision, cell microscopy": ["medical", "biological", "cell", "microscopy", "mri", "ct"],
    "Multimodal learning": ["multimodal", "multi-modal", "vision-language", "audio-visual"],
    "Optimization methods (other than deep learning)": ["optimization", "solver", "gradient", "convex"],
    "Photogrammetry and remote sensing": ["remote sensing", "satellite", "aerial", "photogrammetry"],
    "Physics-based vision and shape-from-X": ["physics", "shape-from", "reflectance", "inverse rendering"],
    "Recognition: Categorization, detection, retrieval": ["recognition", "classification", "detection", "retrieval", "re-identification"],
    "Representation learning": ["representation", "embedding", "feature learning", "pretraining"],
    "Computer Vision for Robotics": ["robot", "robotics", "grasp", "manipulation"],
    "Scene analysis and understanding": ["scene", "understanding", "layout", "affordance"],
    "Segmentation, grouping and shape analysis": ["segmentation", "mask", "grouping", "shape analysis"],
    "Self-, semi-, meta- and unsupervised learning": ["self-supervised", "semi-supervised", "unsupervised", "meta-learning"],
    "Transfer/ low-shot/ continual/ long-tail learning": ["transfer", "few-shot", "low-shot", "continual", "long-tail", "domain adaptation"],
    "Transparency, fairness, accountability, privacy and ethics in vision": ["fairness", "privacy", "ethics", "accountability", "transparency"],
    "Video: Action and event understanding": ["action recognition", "event understanding", "activity"],
    "Video: Low-level analysis, motion, and tracking": ["video", "tracking", "motion", "optical flow", "temporal"],
    "Vision + graphics": ["graphics", "rendering", "gaussian splatting", "nerf", "mesh", "animation"],
    "Vision, language, and reasoning": ["language", "reasoning", "vqa", "caption", "instruction", "llm"],
    "Vision applications and systems": ["application", "system", "deployment", "real-time"],
}

PROMPT = """# Role
당신은 Computer Vision, Machine Learning, Graphics, Multimodal AI 분야의 전문 연구원입니다.
주어진 논문 텍스트를 바탕으로 연구의 Problem, Method, Experiment, Contribution, Limitation을 기술적으로 정확하고 구조적으로 명확하게 분석하세요.
목표는 Abstract를 단순 번역하거나 축약하는 것이 아니라, 연구자가 빠르게 다음을 이해할 수 있도록 만드는 것입니다.

- 이 논문이 해결하려는 핵심 문제는 무엇인가?
- 기존 접근의 한계는 무엇인가?
- 저자들이 제안한 핵심 아이디어와 구조는 무엇인가?
- 실제 구현에서 중요한 Module, Loss, Training Strategy, Inference Flow는 무엇인가?
- 어떤 Dataset, Benchmark, Metric에서 효과를 보였는가?
- 어떤 조건에서 강하고, 어떤 한계가 있는가?
- 이 논문이 실제 프로젝트나 후속 연구에 어떻게 활용될 수 있는가?

# Critical Writing Rules
1. Technical Terminology in English: 논문에 등장하는 핵심 기술 용어, Model 이름, Module 이름, Metric, Dataset, Benchmark, Loss, Architecture, Algorithm 이름은 억지로 한국어로 번역하지 말고 English 원문 그대로 사용하세요.
2. Natural Korean Phrasing: 전체 문장은 자연스러운 한국어로 작성하되, 명사나 핵심 동사는 English technical terminology를 섞는 전문 문체를 유지하세요.
3. Evidence-Based Analysis: Abstract 표현만 반복하지 말고 Method, Figure, Table, Experiment, Ablation을 종합해서 해석하세요.
4. No Hallucination: 논문 원문에 없는 Hyperparameter, Training Cost, Dataset 규모, Hardware 정보, Code 공개 여부 등을 추측해서 채우지 마세요.
5. Eight-Line Summary First: 요약 본문 맨 앞에는 [0. Eight-Line Paper Summary] 섹션을 반드시 작성하세요.
6. Mandatory Terminology Section: 8줄 요약 다음에는 [1. Key Terms & Definitions] 섹션을 반드시 작성하세요.
7. Output Format Compliance: 아래 섹션 구조만 출력하고, 별도의 서론/후기/사과문은 쓰지 마세요.

# Uncertainty Markers
원문에 근거가 부족한 경우 다음 표현 중 하나를 사용하세요.
- 논문 본문에서 명확히 확인되지 않음
- 저자 주장으로 보이나 정량 근거는 제한적임
- 추론 가능하지만 명시적으로 서술되지는 않음
- 본문 excerpt에서 명시적 수치를 확인하지 못함

# Analysis Checklist
논문 텍스트에서 확인 가능한 경우 반드시 반영하세요. 단, 확인되지 않는 항목은 억지로 만들지 말고 위 Uncertainty Marker로 표시하세요.

- Problem Formulation
- Input / Output
- Model Architecture
- Core Module
- Data Flow / Pipeline
- Training Objective
- Loss Function
- Optimization Strategy
- Dataset / Benchmark
- Evaluation Protocol
- Metric
- Baseline / SOTA comparison
- Ablation Study
- Inference Pipeline
- Computational Cost
- Failure Case
- Limitation
- Generalization
- Real-world Applicability

수식이 등장하는 경우 수식을 길게 복사하지 말고, 이 수식이 최적화하려는 대상, 각 항의 역할, 기존 방식과의 차이, 실제 모델 동작에서의 의미를 풀어서 설명하세요.

# Paper Metadata
Title: {title}
Authors: {authors}
CVF URL: {html_url}
PDF URL: {pdf_url}

# Output Format
## 0. Eight-Line Paper Summary (논문 8줄 요약)
아래 형식을 정확히 지켜 논문을 8줄로 설명하세요. 각 항목은 1문장으로 작성하고, 핵심 technical term은 English 원문을 유지하세요.

1. **Task**: 이 논문이 다루는 Task와 문제 영역을 설명하세요.
2. **Problem**: 기존 연구 또는 Baseline이 해결하지 못한 핵심 한계를 설명하세요.
3. **Motivation**: 왜 이 문제가 학술적/실용적으로 중요한지 설명하세요.
4. **Core Idea**: 제안 방법의 가장 중요한 아이디어를 설명하세요.
5. **Method**: 핵심 architecture, module, pipeline 중 가장 중요한 설계를 설명하세요.
6. **Training / Inference**: Training objective, loss, inference flow 중 논문에서 중요한 구현 포인트를 설명하세요.
7. **Result**: 가장 중요한 정량 결과, Benchmark, Metric, Baseline 대비 개선점을 설명하세요.
8. **Impact / Limitation**: 연구의 시사점과 적용 시 주의해야 할 한계 또는 확인 필요 사항을 설명하세요.

## 1. Key Terms & Definitions (핵심 용어 및 정의)
논문 이해에 반드시 필요한 핵심 용어 3~5개를 선정하여 Markdown table로 정리하세요.

| Term | Definition | Paper Context |
| --- | --- | --- |
| [Term 1] | 간결한 정의 | 이 논문에서 어떤 역할을 하는지 |
| [Term 2] | 간결한 정의 | 이 논문에서 어떤 역할을 하는지 |
| [Term 3] | 간결한 정의 | 이 논문에서 어떤 역할을 하는지 |

## 2. Motivation & Problem Statement (연구 배경 및 문제 정의)
다음을 포함해 2~4문단으로 분석하세요.

- 해결하려는 Task와 Problem Formulation
- Input / Output이 무엇인지
- 기존 접근 또는 Baseline의 한계
- 왜 이 문제가 학술적/실용적으로 중요한지
- 기존 접근의 한계를 아래 table로 요약

| Existing Approach | Limitation | Why It Matters |
| --- | --- | --- |
| [방법 또는 계열] | 한계 | 실제 문제에 미치는 영향 |

## 3. Method & Key Results (제안 방법론 및 핵심 결과)
Method와 Experiment를 함께 분석하되, 주장과 정량 근거를 구분하세요.

### Core Idea
핵심 아이디어를 3~5개 bullet로 정리하세요. 각 항목은 무엇을 제안하는지, 왜 필요한지, 기존 방식과 무엇이 다른지 포함해야 합니다.

### Method / Pipeline
가능하면 전체 흐름을 다음 형식으로 설명하세요.

```text
Input
→ Preprocessing / Representation
→ Core Module / Backbone
→ Interaction / Fusion / Optimization
→ Output
```

핵심 Component가 명확하면 아래 table을 작성하세요.

| Component | Role | Input | Output | Key Design Choice |
| --- | --- | --- | --- | --- |
| [Module 1] | 역할 | 입력 | 출력 | 핵심 설계 |
| [Module 2] | 역할 | 입력 | 출력 | 핵심 설계 |

Loss Function, Training Strategy, Inference Pipeline이 논문에 명시되어 있으면 별도 bullet로 설명하세요.

### Quantitative Results
주요 실험 결과를 가능한 한 정확한 수치로 작성하세요. Dataset, Metric, Baseline, Proposed Method, Improvement를 구분하세요.

| Dataset / Benchmark | Metric | Baseline | Proposed Method | Improvement | Interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| [Dataset] | [Metric] | [value] | [value] | [delta] | 의미 |

Ablation Study가 있다면 어떤 Module이 실제 성능 향상에 가장 크게 기여했는지 설명하세요. 성능 향상이 특정 Dataset이나 Metric에 제한된다면 명확히 언급하세요.

## 4. Conclusion & Impact (결론 및 시사점)
최종 결론, Contribution, Limitation, 활용 가능성을 균형 있게 정리하세요.

- 핵심 Contribution 3개 이하
- Author-Stated Limitation과 분석상 추론되는 Risk를 구분
- Dataset Bias, Computational Cost, Scalability, Domain Shift, Real-time 적용 가능성, Reproducibility Risk 중 관련 있는 항목만 언급
- 실제 Product 또는 후속 Research에 어떻게 활용될 수 있는지
- 적용 시 주의할 Input 조건, Compute Resource, Dataset 의존성

마지막 문단은 다음 관점을 포함해 작성하세요.
이 논문은 [문제 영역]에서 [핵심 기여]를 제공한다. 특히 [가장 강한 장점] 측면에서 의미가 있으나, [가장 중요한 한계 또는 확인 필요 사항] 때문에 실제 적용 시 [주의 사항]을 검토해야 한다.

# Paper Text
{text}
"""


BASIC_PROMPT = """# Role
당신은 Computer Vision, Machine Learning, Graphics, Multimodal AI 분야의 전문 연구원입니다.
주어진 논문 텍스트를 바탕으로, 연구자가 빠르게 훑어볼 수 있는 짧은 한국어 논문 분석 카드를 작성하세요.

# Critical Writing Rules
1. 전체 문장은 자연스러운 한국어로 작성하세요.
2. 핵심 기술 용어, 모델명, 방법론명, 데이터셋, 메트릭은 English 원문을 유지하세요.
3. Abstract만 반복하지 말고 Method, Experiment, Contribution을 종합해 해석하세요.
4. 논문에 없는 내용은 추측하지 마세요.
5. 출력은 반드시 아래 Output Format만 따르고, 별도의 서론/후기/사과문은 쓰지 마세요.

# Paper Metadata
Title: {title}
Authors: {authors}
CVF URL: {html_url}
PDF URL: {pdf_url}

# Output Format
[짧고 눈길 가는 한국어 제목]
논문명: {title}
저자: {authors}

기술 키워드: [핵심 키워드 3~5개를 comma-separated로 작성]

💭💭 이런 질문을 해본 적 있나요?

• [이 논문이 던지는 실용적/연구적 질문 1]
• [이 논문이 던지는 실용적/연구적 질문 2]
• [이 논문이 던지는 실용적/연구적 질문 3]

특히 주목할 점:

→ [핵심 contribution 또는 method 포인트 1]
→ [핵심 contribution 또는 method 포인트 2]
→ [핵심 contribution 또는 method 포인트 3]

🎯🎯 GAME CHANGER

[기존 방식의 한계] → [이 논문이 제안하는 변화 또는 가능성]

# Paper Text
{text}
"""


def build_summary_prompt(
    summary_format: str,
    title: str,
    authors: str,
    html_url: str,
    pdf_url: str,
    text: str,
) -> str:
    prompt_template = BASIC_PROMPT if summary_format == "basic" else PROMPT
    return prompt_template.format(
        title=title,
        authors=authors,
        html_url=html_url,
        pdf_url=pdf_url,
        text=text,
    )


def fetch_text(url: str, retries: int = 3) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:  # network errors should retry
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")


def download(url: str, path: Path, retries: int = 3) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, path.open("wb") as f:
                shutil.copyfileobj(resp, f)
            return
        except Exception as exc:
            last = exc
            if path.exists():
                path.unlink()
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed to download {url}: {last}")


def clean_html_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def parse_papers(list_html: str) -> list[dict[str, Any]]:
    blocks = re.findall(r'<dt class="ptitle">.*?(?=<dt class="ptitle">|\Z)', list_html, flags=re.S)
    papers: list[dict[str, Any]] = []
    for idx, block in enumerate(blocks, start=1):
        title_match = re.search(r'<dt class="ptitle"><br><a href="([^"]+)">(.*?)</a></dt>', block, flags=re.S)
        if not title_match:
            continue
        html_path, raw_title = title_match.groups()
        title = clean_html_text(raw_title)
        authors = [html.unescape(a) for a in re.findall(r'name="query_author" value="([^"]+)"', block)]
        links = {}
        for href, label in re.findall(r'<a(?: [^>]*)? href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S):
            label_text = clean_html_text(label).lower()
            if label_text in {"pdf", "supp"}:
                links[label_text] = urllib.parse.urljoin(BASE_URL, href)
        bibtex_match = re.search(r'<div class="bibref pre-white-space">(.*?)</div>', block, flags=re.S)
        pages_match = re.search(r'pages\s*=\s*\{([^}]+)\}', html.unescape(bibtex_match.group(1)) if bibtex_match else "")
        papers.append({
            "index": idx,
            "title": title,
            "authors": authors,
            "html_url": urllib.parse.urljoin(BASE_URL, html_path),
            "pdf_url": links.get("pdf"),
            "supp_url": links.get("supp"),
            "pages": pages_match.group(1) if pages_match else None,
            "bibtex": html.unescape(bibtex_match.group(1)).strip() if bibtex_match else None,
        })
    return papers


def slugify(title: str, max_len: int = 90) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9가-힣]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return (s[:max_len].strip("-") or "paper")


def title_filename(title: str, max_len: int = 180) -> str:
    s = html.unescape(title)
    s = re.sub(r'[\\/:*?"<>|]+', " ", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".")
    return (s[:max_len].strip().rstrip(".") or "paper")


def scrape(index_path: Path) -> list[dict[str, Any]]:
    text = fetch_text(LIST_URL)
    papers = parse_papers(text)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")
    return papers


def load_index(index_path: Path) -> list[dict[str, Any]]:
    if not index_path.exists():
        return scrape(index_path)
    return json.loads(index_path.read_text(encoding="utf-8"))


def resolve_pdftotext_command(explicit: str | None = None) -> str | None:
    candidates = [explicit, os.environ.get("PDFTOTEXT"), shutil.which("pdftotext")]
    candidates.extend(str(path) for path in WINDOWS_PDFTOTEXT_CANDIDATES)
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
        if shutil.which(candidate):
            return candidate
    return None


def extract_pdf_text(pdf_path: Path, txt_path: Path, pdftotext_cmd: str = "pdftotext") -> str:
    if txt_path.exists() and txt_path.stat().st_size > 0:
        return txt_path.read_text(encoding="utf-8", errors="replace")
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([pdftotext_cmd, "-layout", "-nopgbrk", str(pdf_path), str(txt_path)], check=True)
    return txt_path.read_text(encoding="utf-8", errors="replace")


def resolve_codex_command(explicit: str | None = None) -> str | None:
    candidates = [explicit, DEFAULT_CODEX_COMMAND, shutil.which("codex")]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
        if shutil.which(candidate):
            return candidate
    return None


def build_codex_command(codex_cmd: str, model: str | None, output_path: Path) -> list[str]:
    cmd = [
        codex_cmd,
        "exec",
        "--skip-git-repo-check",
        "-s",
        "read-only",
        "--output-last-message",
        str(output_path),
        "-C",
        str(Path.cwd()),
    ]
    if model:
        cmd.extend(["-m", model])
    cmd.append("-")
    return cmd


def codex_completion(model: str | None, prompt: str, codex_cmd: str | None = None) -> str:
    resolved_codex = resolve_codex_command(codex_cmd)
    if not resolved_codex:
        raise RuntimeError("codex CLI command not found")

    output_path = Path(".codex_summary_output.md")
    if output_path.exists():
        output_path.unlink()

    cmd = build_codex_command(resolved_codex, model, output_path)

    result = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "codex exec failed\n"
            f"stdout:\n{result.stdout[-2000:]}\n"
            f"stderr:\n{result.stderr[-2000:]}"
        )
    if output_path.exists():
        summary = output_path.read_text(encoding="utf-8").strip()
        output_path.unlink()
    else:
        summary = result.stdout.strip()
    if not summary:
        raise RuntimeError("codex exec produced an empty summary")
    return summary


def normalize_category(value: str | None) -> str | None:
    if not value:
        return None
    return CATEGORY_ALIASES.get(value.strip().casefold())


def parse_category_response(response: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", response, flags=re.S)
    if not match:
        raise RuntimeError(f"category response did not contain JSON: {response[:200]}")
    payload = json.loads(match.group(0))
    primary = normalize_category(payload.get("primary_category"))
    if not primary:
        primary = "Vision applications and systems"

    secondary: list[str] = []
    for raw in payload.get("secondary_categories") or []:
        category = normalize_category(raw)
        if category and category != primary and category not in secondary:
            secondary.append(category)
        if len(secondary) >= 2:
            break

    confidence = payload.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "primary_category": primary,
        "secondary_categories": secondary,
        "confidence": confidence,
        "reason": str(payload.get("reason") or "").strip()[:500],
    }


def category_prompt(paper: dict[str, Any], text_excerpt: str) -> str:
    categories = "\n".join(f"- {category}" for category in CVPR2026_CATEGORIES)
    authors = ", ".join(paper.get("authors") or [])
    return f"""Classify this CVPR 2026 paper into the official CVPR 2026 topic taxonomy.

Return only JSON with these fields:
- primary_category: exactly one category from the official list
- secondary_categories: up to two additional exact categories from the official list
- confidence: number from 0.0 to 1.0
- reason: one short sentence

Official categories:
{categories}

Paper:
Title: {paper.get("title", "")}
Authors: {authors}
CVF URL: {paper.get("html_url", "")}

Text excerpt:
{text_excerpt[:20000]}
"""


def classify_paper_with_keywords(paper: dict[str, Any], text_excerpt: str = "") -> dict[str, Any]:
    haystack = " ".join(
        [
            paper.get("title", ""),
            " ".join(paper.get("authors") or []),
            text_excerpt[:5000],
        ]
    ).casefold()
    scores: list[tuple[int, str]] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.casefold() in haystack)
        if score:
            scores.append((score, category))
    scores.sort(key=lambda item: (-item[0], CVPR2026_CATEGORIES.index(item[1])))
    if not scores:
        return {
            "primary_category": "Vision applications and systems",
            "secondary_categories": [],
            "confidence": 0.2,
            "reason": "No strong keyword match; assigned to the broad applications/systems category.",
        }
    primary = scores[0][1]
    secondary = [category for _, category in scores[1:3]]
    return {
        "primary_category": primary,
        "secondary_categories": secondary,
        "confidence": min(0.95, 0.45 + 0.15 * scores[0][0]),
        "reason": "Keyword fallback classification based on title and available paper text.",
    }


def classification_from_metadata(paper: dict[str, Any]) -> dict[str, Any] | None:
    primary = normalize_category(paper.get("primary_category"))
    if not primary:
        return None
    secondary: list[str] = []
    for raw in paper.get("secondary_categories") or []:
        category = normalize_category(raw)
        if category and category != primary and category not in secondary:
            secondary.append(category)
        if len(secondary) >= 2:
            break
    return {
        "primary_category": primary,
        "secondary_categories": secondary,
        "confidence": float(paper.get("confidence") or 1.0),
        "reason": str(paper.get("reason") or "Category already present in paper metadata."),
        "category_source": "metadata",
    }


def text_excerpt_for_paper(paper: dict[str, Any], text_dir: Path) -> str:
    cache_slug = f"{paper['index']:04d}-{slugify(paper['title'])}"
    txt_path = text_dir / f"{cache_slug}.txt"
    if not txt_path.exists():
        return ""
    return txt_path.read_text(encoding="utf-8", errors="replace")[:20000]


def classify_paper(paper: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    text_excerpt = text_excerpt_for_paper(paper, args.text_dir)
    if args.category_classifier == "codex":
        response = codex_completion(args.model, category_prompt(paper, text_excerpt), args.codex)
        classification = parse_category_response(response)
        classification["category_source"] = "codex"
    elif args.category_classifier == "keywords":
        classification = classify_paper_with_keywords(paper, text_excerpt)
        classification["category_source"] = "keywords"
    else:
        classification = classification_from_metadata(paper)
        if not classification:
            keyword_classification = classify_paper_with_keywords(paper, text_excerpt)
            threshold = getattr(args, "hybrid_confidence_threshold", 0.7)
            if keyword_classification["confidence"] >= threshold:
                classification = keyword_classification
                classification["category_source"] = "keywords"
            else:
                response = codex_completion(args.model, category_prompt(paper, text_excerpt), args.codex)
                classification = parse_category_response(response)
                classification["category_source"] = "hybrid_codex"
    return {**paper, **classification}


def build_category_index(args: argparse.Namespace) -> list[dict[str, Any]]:
    papers = load_index(args.index)
    existing: dict[int, dict[str, Any]] = {}
    if args.categories_path.exists() and not args.category_overwrite:
        existing = {
            int(row["index"]): row
            for row in json.loads(args.categories_path.read_text(encoding="utf-8"))
            if "index" in row
        }

    selected = papers[args.start - 1:]
    if not args.all:
        selected = selected[: args.limit]

    updated = dict(existing)
    for paper in selected:
        index = int(paper["index"])
        if index in updated and not args.category_overwrite:
            print(f"category exists: #{index} {paper['title']}")
            continue
        print(f"classifying #{index}: {paper['title']}", flush=True)
        updated[index] = classify_paper(paper, args)
        if args.sleep:
            time.sleep(args.sleep)

    rows = [updated[index] for index in sorted(updated)]
    args.categories_path.parent.mkdir(parents=True, exist_ok=True)
    args.categories_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def category_names(values: list[str]) -> set[str]:
    names: set[str] = set()
    for raw in values:
        value = raw.strip()
        if re.fullmatch(r"\d+", value):
            index = int(value)
            if index < 0 or index >= len(CVPR2026_CATEGORIES):
                raise RuntimeError(f"unknown CVPR category index: {value}")
            category = CVPR2026_CATEGORIES[index]
        else:
            category = normalize_category(value)
        if not category:
            raise RuntimeError(f"unknown CVPR category: {raw}")
        names.add(category)
    return names


def parse_category_selection(raw: str) -> list[str]:
    values = [part.strip() for part in re.split(r"[;,]", raw or "") if part.strip()]
    selected = category_names(values)
    return [category for category in CVPR2026_CATEGORIES if category in selected]


def paper_matches_categories(paper: dict[str, Any], selected_categories: list[str]) -> bool:
    selected = category_names(selected_categories)
    paper_categories = {
        category
        for category in [paper.get("primary_category"), *(paper.get("secondary_categories") or [])]
        if category
    }
    return bool(paper_categories & selected)


def category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {category: 0 for category in CVPR2026_CATEGORIES}
    for row in rows:
        seen = {
            category
            for category in [row.get("primary_category"), *(row.get("secondary_categories") or [])]
            if category in counts
        }
        for category in seen:
            counts[category] += 1
    return counts


def list_categories(args: argparse.Namespace) -> None:
    if not args.categories_path.exists():
        raise RuntimeError(f"category index not found: {args.categories_path}")
    rows = json.loads(args.categories_path.read_text(encoding="utf-8"))
    counts = category_counts(rows)
    for index, category in enumerate(CVPR2026_CATEGORIES):
        print(f"{index:2d}  {counts[category]:4d}  {category}")


def load_category_index(args: argparse.Namespace) -> list[dict[str, Any]]:
    if not args.categories_path.exists():
        raise RuntimeError(f"category index not found: {args.categories_path}")
    rows = json.loads(args.categories_path.read_text(encoding="utf-8"))
    if args.categories:
        requested = parse_category_selection(args.categories)
        rows = [row for row in rows if paper_matches_categories(row, requested)]
    return rows


def write_markdown(paper: dict[str, Any], summary: str, out_path: Path) -> None:
    authors = ", ".join(paper.get("authors") or [])
    front = [
        "---",
        f"title: {json.dumps(paper['title'], ensure_ascii=False)}",
        f"authors: {json.dumps(authors, ensure_ascii=False)}",
        f"cvf_url: {paper['html_url']}",
        f"pdf_url: {paper.get('pdf_url') or ''}",
        f"pages: {paper.get('pages') or ''}",
        "---",
        "",
        f"# {paper['title']}",
        "",
        f"- **Authors**: {authors}",
        f"- **CVF**: {paper['html_url']}",
        f"- **PDF**: {paper.get('pdf_url') or ''}",
        "",
        summary,
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(front), encoding="utf-8")


def strip_markdown_front_matter(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[index + 1:]).lstrip()
    return markdown


def render_markdown_inline(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    return escaped


def render_markdown_table(lines: list[str]) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if not rows:
        return ""
    header = rows[0]
    body = rows[2:] if len(rows) > 2 else []

    def normalize_row(row: list[str]) -> list[str]:
        if len(row) > len(header):
            row = row[: len(header) - 1] + [" | ".join(row[len(header) - 1:])]
        return row + [""] * (len(header) - len(row))

    parts = ["<table>", "<thead><tr>"]
    parts.extend(f"<th>{render_markdown_inline(cell)}</th>" for cell in header)
    parts.append("</tr></thead>")
    if body:
        parts.append("<tbody>")
        for row in body:
            row = normalize_row(row)
            parts.append("<tr>")
            parts.extend(f"<td>{render_markdown_inline(cell)}</td>" for cell in row)
            parts.append("</tr>")
        parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


def markdown_to_html(markdown: str) -> str:
    lines = strip_markdown_front_matter(markdown).splitlines()
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            index += 1
            blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", lines[index + 1]):
            table_lines = [line, lines[index + 1]]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            blocks.append(render_markdown_table(table_lines))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{render_markdown_inline(heading.group(2))}</h{level}>")
            index += 1
            continue

        if re.match(r"^\s*[-*]\s+", line):
            items: list[str] = []
            while index < len(lines) and re.match(r"^\s*[-*]\s+", lines[index]):
                item = re.sub(r"^\s*[-*]\s+", "", lines[index])
                items.append(f"<li>{render_markdown_inline(item)}</li>")
                index += 1
            blocks.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while index < len(lines) and re.match(r"^\s*\d+\.\s+", lines[index]):
                item = re.sub(r"^\s*\d+\.\s+", "", lines[index])
                items.append(f"<li>{render_markdown_inline(item)}</li>")
                index += 1
            blocks.append("<ol>\n" + "\n".join(items) + "\n</ol>")
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines) and lines[index].strip():
            next_line = lines[index].strip()
            if (
                next_line.startswith("```")
                or next_line.startswith("|")
                or re.match(r"^(#{1,6})\s+", next_line)
                or re.match(r"^\s*[-*]\s+", lines[index])
                or re.match(r"^\s*\d+\.\s+", lines[index])
            ):
                break
            paragraph_lines.append(next_line)
            index += 1
        blocks.append(f"<p>{render_markdown_inline(' '.join(paragraph_lines))}</p>")

    return "\n".join(blocks)


def write_zotero_analysis_html(markdown_path: Path, html_path: Path, title: str) -> None:
    markdown = markdown_path.read_text(encoding="utf-8", errors="replace")
    escaped_title = html.escape(title, quote=True)
    body_html = markdown_to_html(markdown)
    document = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{escaped_title} - CVPR 2026 Analysis</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
      margin: 32px;
      max-width: 980px;
      color: #1f2328;
      background: #ffffff;
    }}
    h1, h2, h3 {{ line-height: 1.25; margin-top: 1.6em; }}
    h1 {{ font-size: 26px; }}
    h2 {{ font-size: 21px; border-bottom: 1px solid #d0d7de; padding-bottom: 6px; }}
    h3 {{ font-size: 17px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
    th, td {{ border: 1px solid #d0d7de; padding: 7px 9px; vertical-align: top; }}
    th {{ background: #f6f8fa; font-weight: 600; }}
    code {{ background: #f6f8fa; padding: 1px 4px; border-radius: 4px; }}
    pre {{ background: #f6f8fa; padding: 12px; overflow-x: auto; }}
    a {{ color: #0969da; }}
  </style>
</head>
<body>
{body_html}
</body>
</html>
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(document, encoding="utf-8")


def ris_escape(value: Any) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return " ".join(text.split())


def ris_lines(tag: str, values: list[Any]) -> list[str]:
    return [f"{tag}  - {ris_escape(value)}" for value in values if ris_escape(value)]


def safe_path_name(value: str, max_len: int = 120) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', " ", value)
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return (text[:max_len].strip().rstrip(".") or "category")


def page_parts(pages: str | None) -> tuple[str, str]:
    if not pages:
        return "", ""
    parts = [part.strip() for part in pages.split("-", 1)]
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def build_ris_entry(
    paper: dict[str, Any],
    pdf_path: Path | None,
    analysis_html_path: Path | None = None,
) -> str:
    start_page, end_page = page_parts(paper.get("pages"))
    lines = [
        "TY  - CONF",
        f"T1  - {ris_escape(paper.get('title'))}",
        "T2  - Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)",
        "PY  - 2026",
        "DA  - 2026/06",
    ]
    lines.extend(ris_lines("AU", paper.get("authors") or []))
    lines.extend(ris_lines("SP", [start_page]))
    lines.extend(ris_lines("EP", [end_page]))
    lines.extend(ris_lines("UR", [paper.get("html_url") or paper.get("pdf_url")]))
    lines.extend(ris_lines("DO", [paper.get("doi")]))
    categories = [paper.get("primary_category"), *(paper.get("secondary_categories") or [])]
    lines.extend(ris_lines("KW", ["CVPR 2026", *categories]))
    if pdf_path and pdf_path.exists():
        lines.append(f"L1  - {pdf_path.resolve().as_uri()}")
    if analysis_html_path and analysis_html_path.exists():
        lines.append(f"L2  - {analysis_html_path.resolve().as_uri()}")
    lines.append("ER  -")
    return "\n".join(lines) + "\n"


def build_category_zotero_exports(
    rows: list[dict[str, Any]],
    selected_categories: list[str],
    zotero_dir: Path,
    pdf_dir: Path,
    output_dir: Path,
) -> dict[str, dict[str, Any]]:
    selected = sorted(category_names(selected_categories), key=CVPR2026_CATEGORIES.index)
    base_dir = zotero_dir / "by_category"
    base_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, dict[str, Any]] = {}

    for category in selected:
        category_rows = [row for row in rows if paper_matches_categories(row, [category])]
        category_dir = base_dir / safe_path_name(category)
        category_dir.mkdir(parents=True, exist_ok=True)
        ris_path = category_dir / "import.ris"
        report_path = category_dir / "report.json"
        entries: list[str] = []
        report: list[dict[str, Any]] = []

        for paper in category_rows:
            cache_slug = f"{paper['index']:04d}-{slugify(paper['title'])}"
            pdf_path = pdf_dir / f"{cache_slug}.pdf"
            md_path = output_dir / f"{title_filename(paper['title'])}.md"
            analysis_html_path = zotero_dir / "analysis_html" / f"{title_filename(paper['title'])}.html"
            if md_path.exists():
                write_zotero_analysis_html(md_path, analysis_html_path, paper["title"])
            entries.append(
                build_ris_entry(
                    paper,
                    pdf_path if pdf_path.exists() else None,
                    analysis_html_path if analysis_html_path.exists() else None,
                )
            )
            report.append(
                {
                    "index": paper["index"],
                    "title": paper["title"],
                    "target_category": category,
                    "primary_category": paper.get("primary_category"),
                    "secondary_categories": paper.get("secondary_categories") or [],
                    "pdf_path": str(pdf_path.resolve()) if pdf_path.exists() else None,
                    "markdown_path": str(md_path.resolve()) if md_path.exists() else None,
                    "analysis_html_path": str(analysis_html_path.resolve()) if analysis_html_path.exists() else None,
                    "html_url": paper.get("html_url"),
                    "pdf_url": paper.get("pdf_url"),
                }
            )

        ris_path.write_text("\n".join(entries), encoding="utf-8")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs[category] = {"ris_path": ris_path, "report_path": report_path, "count": len(category_rows)}

    return outputs


def prepare_zotero_import_by_category(args: argparse.Namespace) -> None:
    if not args.categories:
        raise RuntimeError("category selection is required")
    requested = parse_category_selection(args.categories)
    rows = load_category_index(args)
    outputs = build_category_zotero_exports(rows, requested, args.zotero_dir, args.pdf_dir, args.output)
    for category, payload in outputs.items():
        print(f"{payload['count']:4d}  {category}")
        print(f"      RIS: {payload['ris_path']}")
        print(f"   report: {payload['report_path']}")


def summarize(args: argparse.Namespace) -> None:
    pdftotext_cmd = resolve_pdftotext_command(args.pdftotext)
    if not pdftotext_cmd:
        raise RuntimeError(
            "pdftotext command not found. Add it to PATH, set PDFTOTEXT, or pass --pdftotext."
        )
    papers = load_category_index(args) if args.categories else load_index(args.index)
    selected = papers[args.start - 1:]
    if not args.all:
        selected = selected[: args.limit]
    for paper in selected:
        if not paper.get("pdf_url"):
            print(f"skip #{paper['index']}: no pdf", file=sys.stderr)
            continue
        cache_slug = f"{paper['index']:04d}-{slugify(paper['title'])}"
        out_md = args.output / f"{title_filename(paper['title'])}.md"
        if out_md.exists() and not args.overwrite:
            print(f"exists: {out_md}")
            continue
        pdf_path = args.pdf_dir / f"{cache_slug}.pdf"
        txt_path = args.text_dir / f"{cache_slug}.txt"
        print(f"processing #{paper['index']}: {paper['title']}", flush=True)
        download(paper["pdf_url"], pdf_path)
        text = extract_pdf_text(pdf_path, txt_path, pdftotext_cmd)
        text = text[: args.max_chars]
        prompt = build_summary_prompt(
            summary_format=args.summary_format,
            title=paper["title"],
            authors=", ".join(paper.get("authors") or []),
            html_url=paper["html_url"],
            pdf_url=paper.get("pdf_url") or "",
            text=text,
        )
        summary = codex_completion(args.model, prompt, args.codex)
        write_markdown(paper, summary, out_md)
        if args.sleep:
            time.sleep(args.sleep)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, default=Path("data/cvpr2026_index.json"))
    parser.add_argument("--output", type=Path, default=Path("summaries"))
    parser.add_argument("--pdf-dir", type=Path, default=Path("data/pdfs"))
    parser.add_argument("--text-dir", type=Path, default=Path("data/text"))
    parser.add_argument("--categories-path", type=Path, default=DEFAULT_CATEGORIES_PATH)
    parser.add_argument("--categories", help="Semicolon-separated official CVPR categories to select")
    parser.add_argument("--category-classifier", choices=["hybrid", "codex", "keywords"], default="hybrid")
    parser.add_argument(
        "--hybrid-confidence-threshold",
        type=float,
        default=0.7,
        help="Use Codex in hybrid mode when keyword confidence is below this value.",
    )
    parser.add_argument("--category-overwrite", action="store_true")
    parser.add_argument("--zotero-dir", type=Path, default=DEFAULT_ZOTERO_DIR)
    parser.add_argument("--pdftotext", help="Path to pdftotext executable. Overrides PATH lookup.")
    parser.add_argument("--codex", help="Path to codex executable/cmd. Overrides PATH lookup and CODEX_CLI.")
    parser.add_argument("--model", default=DEFAULT_CODEX_MODEL, help="Codex CLI model. Defaults to current Codex config.")
    parser.add_argument(
        "--summary-format",
        choices=["detailed", "basic"],
        default="detailed",
        help="Summary prompt format. 'basic' writes a short paper analysis card.",
    )
    parser.add_argument("--max-chars", type=int, default=120_000)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--all", action="store_true", help="summarize every paper from --start")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--scrape", action="store_true")
    parser.add_argument("--classify-categories", action="store_true")
    parser.add_argument("--list-categories", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args()

    if args.scrape:
        papers = scrape(args.index)
        print(f"scraped {len(papers)} papers -> {args.index}")
    if args.classify_categories:
        rows = build_category_index(args)
        print(f"classified {len(rows)} papers -> {args.categories_path}")
    if args.list_categories:
        list_categories(args)
    if args.summarize:
        summarize(args)
    if not any([args.scrape, args.classify_categories, args.list_categories, args.summarize]):
        parser.print_help()


if __name__ == "__main__":
    main()
