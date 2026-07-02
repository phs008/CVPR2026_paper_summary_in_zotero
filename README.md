# CVPR 2026 Paper Pipeline

CVPR 2026 Open Access 논문 목록을 수집하고, 논문을 CVPR 2026 공식 주제 분류에 맞춰 분류한 뒤, PDF 본문 기반 한국어 Markdown 요약과 Zotero import용 RIS 파일을 만드는 로컬 파이프라인입니다.

이 저장소의 핵심 스크립트는 두 개입니다.

- `cvpr2026_summarize.py`: 논문 목록 수집, 카테고리 분류, PDF 다운로드/텍스트 추출, 요약 Markdown 생성, Zotero용 RIS/HTML 준비
- `cvpr2026_zotero.py`: Zotero Desktop/Connector 상태 확인, 선택된 Zotero 대상 확인, 카테고리별 RIS import 실행

## 처음 실행 순서

처음에는 전체 논문을 한 번에 처리하지 말고, 아래 순서대로 작은 단위로 검증하는 것을 권장합니다.

```powershell
# 1. CVF Open Access 논문 목록 수집
python cvpr2026_summarize.py --scrape

# 2. 논문별 CVPR 2026 카테고리 분류
python cvpr2026_summarize.py --classify-categories --all --sleep 0.5

# 3. 카테고리 번호 확인
python cvpr2026_summarize.py --list-categories

# 4. 특정 카테고리에서 논문 1편만 요약 테스트
python cvpr2026_summarize.py --summarize --categories "16" --limit 1

# 5. Zotero 상태 확인
python cvpr2026_zotero.py status --json

# 6. 현재 선택된 Zotero library/collection 확인
python cvpr2026_zotero.py selected-target --json

# 7. Zotero import도 1편만 먼저 테스트
python cvpr2026_zotero.py import-category 16 --prepare --limit 1
```

`16`은 예시 카테고리 번호입니다. 실제 사용할 번호는 `--list-categories` 출력에서 확인하세요.

## 준비물

- Python 3.10 이상
- `pdftotext` 실행 파일
  - PDF에서 텍스트를 추출할 때 필요합니다.
  - Windows에서는 Git for Windows에 포함된 다음 경로가 자동 후보로 사용됩니다.
    - `C:\Program Files\Git\mingw64\bin\pdftotext.exe`
    - `C:\Program Files\Git\usr\bin\pdftotext.exe`
- 로컬에서 인증된 `codex` CLI
  - 카테고리 분류의 Codex fallback과 논문 요약 생성에 사용됩니다.
- Zotero Desktop
- Zotero Connector local endpoint
  - Zotero import 단계에서 필요합니다.
- 별도 Python 패키지 설치는 현재 필요하지 않습니다. 스크립트는 Python 표준 라이브러리만 사용합니다.

## 출력 경로

| 용도 | 기본 경로 |
| --- | --- |
| 논문 index | `data/cvpr2026_index.json` |
| 카테고리 분류 결과 | `data/cvpr2026_categories.json` |
| PDF cache | `data/pdfs/` |
| PDF 추출 text cache | `data/text/` |
| Markdown 요약 | `summaries/` |
| Zotero 카테고리별 RIS | `data/zotero/by_category/<category>/import.ris` |
| Zotero import report | `data/zotero/by_category/<category>/report.json` |
| Zotero HTML 분석 첨부 | `data/zotero/analysis_html/` |

## 1. 논문 목록 수집

CVF Open Access의 CVPR 2026 전체 논문 목록을 가져와 `data/cvpr2026_index.json`에 저장합니다.

```powershell
python cvpr2026_summarize.py --scrape
```

기본 수집 URL은 스크립트 안의 `LIST_URL`에 정의되어 있습니다.

```text
https://openaccess.thecvf.com/CVPR2026?day=all
```

현재 저장소에는 `data/cvpr2026_index.json`이 이미 생성되어 있습니다. 다시 수집하려면 위 명령을 실행하면 됩니다.

## 2. 카테고리 분류

논문 목록을 CVPR 2026 공식 주제 taxonomy에 맞춰 분류합니다.

### 기본 방식: hybrid

기본값은 `hybrid`입니다.

처리 순서:

1. paper metadata에 `primary_category`가 있으면 그대로 사용
2. 없으면 keyword matching으로 1차 분류
3. keyword confidence가 낮으면 Codex로 재분류

```powershell
python cvpr2026_summarize.py --classify-categories --all --sleep 0.5
```

결과는 다음 파일에 저장됩니다.

```text
data/cvpr2026_categories.json
```

이미 분류된 논문은 기본적으로 건너뜁니다. 다시 분류하려면 `--category-overwrite`를 추가합니다.

```powershell
python cvpr2026_summarize.py --classify-categories --all --category-overwrite --sleep 0.5
```

hybrid 모드에서 Codex fallback 기준은 `--hybrid-confidence-threshold`로 조정합니다. 기본값은 `0.7`입니다.

```powershell
python cvpr2026_summarize.py --classify-categories --all --hybrid-confidence-threshold 0.8 --sleep 0.5
```

### Codex만 사용

모든 대상 논문을 Codex로 분류하려면 다음처럼 실행합니다.

```powershell
python cvpr2026_summarize.py --classify-categories --category-classifier codex --all --sleep 0.5
```

### keyword만 사용

Codex를 사용하지 않고 제목/초록/본문 일부의 keyword matching만 사용하려면 다음처럼 실행합니다.

```powershell
python cvpr2026_summarize.py --classify-categories --category-classifier keywords --all
```

이 방식은 빠르지만 hybrid 또는 Codex 분류보다 정확도가 낮을 수 있습니다.

## 3. 카테고리 번호 확인

카테고리별 논문 수와 zero-based category index를 출력합니다.

```powershell
python cvpr2026_summarize.py --list-categories
```

이후 `--categories`에는 category index 또는 정확한 category name을 넣을 수 있습니다. 여러 개를 지정할 때는 쉼표 또는 세미콜론을 사용할 수 있습니다.

```powershell
python cvpr2026_summarize.py --summarize --categories "34,35" --all --sleep 0.5
```

## 4. 논문 요약 생성

처음에는 1~5편만 실행해 `pdftotext`, `codex`, 출력 형식이 정상인지 확인하세요.

```powershell
python cvpr2026_summarize.py --summarize --limit 5
```

특정 카테고리만 처리하려면 다음처럼 실행합니다.

```powershell
python cvpr2026_summarize.py --summarize --categories "16" --limit 1
```

카테고리 전체를 처리하려면 `--all`을 사용합니다.

```powershell
python cvpr2026_summarize.py --summarize --categories "16" --all --sleep 0.5
```

이미 존재하는 Markdown 요약은 기본적으로 건너뜁니다. 다시 생성하려면 `--overwrite`를 추가합니다.

```powershell
python cvpr2026_summarize.py --summarize --categories "16" --all --overwrite --sleep 0.5
```

### 요약 형식 선택

기본값은 상세 분석 형식입니다.

```powershell
python cvpr2026_summarize.py --summarize --summary-format detailed --limit 5
```

짧은 분석 카드 형식으로 생성하려면 `basic`을 사용합니다.

```powershell
python cvpr2026_summarize.py --summarize --summary-format basic --limit 5
```

## 5. 실행 파일 경로 지정

### `pdftotext` 경로 지정

`pdftotext`가 PATH에서 잡히지 않으면 `--pdftotext`로 직접 지정합니다.

```powershell
python cvpr2026_summarize.py --summarize --categories "16" --limit 1 --pdftotext "C:\Program Files\Git\mingw64\bin\pdftotext.exe"
```

또는 환경 변수로 지정할 수 있습니다.

```powershell
$env:PDFTOTEXT="C:\Program Files\Git\mingw64\bin\pdftotext.exe"
python cvpr2026_summarize.py --summarize --categories "16" --limit 1
```

### `codex` 경로와 model 지정

`codex`가 PATH에서 잡히지 않으면 `--codex`로 직접 지정합니다.

```powershell
python cvpr2026_summarize.py --summarize --categories "16" --limit 1 --codex "C:\Users\hungsik\AppData\Roaming\npm\codex.cmd"
```

또는 환경 변수로 지정할 수 있습니다.

```powershell
$env:CODEX_CLI="C:\Users\hungsik\AppData\Roaming\npm\codex.cmd"
python cvpr2026_summarize.py --summarize --categories "16" --limit 1
```

Codex model은 `--model` 또는 `CODEX_MODEL` 환경 변수로 지정합니다.

```powershell
python cvpr2026_summarize.py --summarize --limit 5 --model gpt-5.5
```

```powershell
$env:CODEX_MODEL="gpt-5.5"
python cvpr2026_summarize.py --summarize --limit 5
```

## 6. Zotero 연동

`cvpr2026_zotero.py`는 Zotero 관련 작업만 담당하는 wrapper입니다.

카테고리별 RIS 파일을 준비하고, Zotero Connector를 통해 현재 선택된 Zotero target으로 import합니다.

### Zotero 상태 확인

```powershell
python cvpr2026_zotero.py status --json
```

### 현재 선택된 Zotero library/collection 확인

```powershell
python cvpr2026_zotero.py selected-target --json
```

### 카테고리별 RIS 준비

```powershell
python cvpr2026_zotero.py prepare-category 16
```

생성 파일:

```text
data/zotero/by_category/<category>/import.ris
data/zotero/by_category/<category>/report.json
```

요약 Markdown이 이미 있으면 Zotero에서 읽기 쉬운 HTML attachment도 함께 생성됩니다.

```text
data/zotero/analysis_html/<paper title>.html
```

### Zotero import 테스트

bulk import 전에 반드시 1편만 먼저 가져와 Zotero UI에서 결과를 확인하세요.

```powershell
python cvpr2026_zotero.py import-category 16 --prepare --limit 1
```

확인 항목:

- 논문 item이 원하는 library/collection에 들어갔는지
- author/title/year/conference metadata가 기대대로 매핑됐는지
- PDF attachment가 붙었는지
- HTML analysis attachment가 붙었는지

### 카테고리 전체 import

1편 테스트가 정상이라면 같은 카테고리를 전체 import합니다.

```powershell
python cvpr2026_zotero.py import-category 16 --prepare
```

주의: Zotero Connector RIS import가 항상 현재 선택 collection에 item을 배치한다고 보장할 수 없습니다. `--limit 1` 테스트 후 Zotero UI에서 import 결과를 확인한 다음 bulk import를 진행하세요.

## 주요 옵션 요약

### `cvpr2026_summarize.py`

| 옵션 | 의미 |
| --- | --- |
| `--scrape` | CVF Open Access 목록을 수집해 index JSON 생성 |
| `--classify-categories` | 논문별 CVPR 2026 category 분류 |
| `--category-classifier hybrid\|codex\|keywords` | hybrid, Codex 전용, keyword 전용 분류 선택 |
| `--hybrid-confidence-threshold` | hybrid mode에서 Codex fallback을 사용할 confidence 기준 |
| `--category-overwrite` | 기존 category 결과를 덮어쓰기 |
| `--list-categories` | category index와 논문 수 출력 |
| `--summarize` | PDF 다운로드, text 추출, Codex 요약 생성 |
| `--categories` | category index/name 필터 |
| `--start` | 1-based 시작 위치 |
| `--limit` | `--all`이 없을 때 처리할 개수 |
| `--all` | `--start` 이후 모든 항목 처리 |
| `--overwrite` | 기존 summary Markdown 재생성 |
| `--sleep` | 항목 사이 대기 시간 |
| `--summary-format detailed\|basic` | 상세 분석 또는 기본 분석 카드 prompt 선택 |
| `--max-chars` | Codex prompt에 넣을 PDF text 최대 길이 |
| `--pdftotext` | `pdftotext` 실행 파일 경로 |
| `--codex` | `codex` 실행 파일 경로 |
| `--model` | Codex model 지정 |

### `cvpr2026_zotero.py`

| 명령 | 의미 |
| --- | --- |
| `status` | Zotero Connector/local API 상태 확인 |
| `selected-target` | 현재 선택된 Zotero library/collection 확인 |
| `prepare-category <category>` | 카테고리별 RIS/report/analysis HTML 준비 |
| `import-category <category>` | 카테고리별 RIS를 Zotero로 import |

`import-category`에서 자주 쓰는 옵션:

| 옵션 | 의미 |
| --- | --- |
| `--prepare` | import 전에 RIS를 다시 생성 |
| `--limit N` | 앞에서 N개만 import |

## 결과 Markdown 형식

각 논문 요약은 `summaries/<paper title>.md`로 저장됩니다.

기본 상세 요약은 Markdown front matter와 함께 다음 섹션을 포함하도록 prompt가 구성되어 있습니다.

0. Eight-Line Paper Summary
1. Key Terms & Definitions
2. Motivation & Problem Statement
3. Method & Key Results
4. Conclusion & Impact

Zotero용 RIS에는 가능한 경우 다음 정보가 포함됩니다.

- 논문 제목, 저자, 학회명, 연도, page, URL
- `CVPR 2026` 및 category keyword
- 로컬 PDF attachment (`L1`)
- 요약 HTML attachment (`L2`)

## 권장 smoke test

새 환경에서 가장 먼저 확인할 최소 흐름입니다.

```powershell
python cvpr2026_summarize.py --help
python cvpr2026_zotero.py --help
python cvpr2026_summarize.py --list-categories
python cvpr2026_summarize.py --summarize --categories "16" --limit 1
python cvpr2026_zotero.py status --json
python cvpr2026_zotero.py selected-target --json
python cvpr2026_zotero.py import-category 16 --prepare --limit 1
```
