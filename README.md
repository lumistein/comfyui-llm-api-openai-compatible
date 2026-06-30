# ☁️ comfyui-llm-api-openai-compatible

ComfyUI 커스텀 노드 — OpenAI 호환 API로 클라우드 LLM 사용

OpenAI, Anthropic, Google Gemini (OpenAI proxy), Ollama, LM Studio 등 **OpenAI Chat Completions 형식**을 지원하는 모든 서비스와 연동할 수 있습니다.

---

## 설치

1. 이 폴더를 ComfyUI의 `custom_nodes/` 디렉터리에 복사합니다:
   ```
   ComfyUI/
   └── custom_nodes/
       └── comfyui-llm-api-openai-compatible/   ← 여기
   ```
2. ComfyUI를 재시작합니다.
3. 노드 검색창에서 **"Cloud LLM"** 또는 **"LLM"** 으로 검색하면 나타납니다.
   - 카테고리: `LLM / API`
   - 표시 이름: `☁️ Cloud LLM (OpenAI-compatible)`

> **별도 패키지 설치 불필요.** Python 기본 내장 라이브러리(`urllib`)만 사용합니다.

---

## 노드 입력 설명

| 필드 | 설명 |
|---|---|
| `base_url` | API 엔드포인트 베이스 URL. `/v1/chat/completions` 는 자동으로 붙습니다. |
| `model` | 모델 ID (예: `gpt-4o-mini`, `claude-3-5-sonnet-20241022`) |
| `api_key` | API 키. 로컬 서버처럼 인증이 없으면 비워 두세요. |
| `prompt_file` | 노드 폴더 안의 `.txt` 파일 목록에서 선택. ChatML 형식 템플릿입니다. |
| `prompt` | `{{prompt_here}}` 자리에 들어갈 사용자 입력 텍스트 |
| `max_tokens` | 응답 최대 토큰 수 (기본값: 1024) |
| `temperature` | 샘플링 온도 0~2 (기본값: 0.7) |

**출력**: `STRING` — 어시스턴트의 응답 텍스트. `Text Concatenate`, `Show Text` 등 STRING 입력을 받는 노드에 바로 연결 가능합니다.

---

## 프롬프트 템플릿 (ChatML 형식)

노드 폴더 안에 `.txt` 파일을 원하는 만큼 만들 수 있습니다.  
파일은 반드시 **ChatML 형식**을 따라야 합니다:

```
<|im_start|>system
여기에 시스템 프롬프트를 씁니다.
<|im_end|>
<|im_start|>user
{{prompt_here}}
<|im_end|>
```

- `{{prompt_here}}` 위치에 노드의 `prompt` 입력값이 삽입됩니다.
- 마지막에 `<|im_start|>assistant` 를 추가하면 assistant 접두어 강제 적용(prefill)이 됩니다 (모델/서비스에 따라 지원 여부 다름).

### 예시 — 번역 봇

```
<|im_start|>system
사용자가 제공하는 텍스트를 영어로 번역해라. 번역문만 출력하고, 부연 설명은 하지 마라.
<|im_end|>
<|im_start|>user
{{prompt_here}}
<|im_end|>
```

### 예시 — 프롬프트 생성기 (이미지 생성용)

```
<|im_start|>system
You are an expert Stable Diffusion prompt engineer.
Convert the user's idea into a detailed English image generation prompt.
Output only the prompt, nothing else.
<|im_end|>
<|im_start|>user
{{prompt_here}}
<|im_end|>
```

---

## 주요 서비스 연동 예시

| 서비스 | base_url | model 예시 |
|---|---|---|
| OpenAI | `https://api.openai.com` | `gpt-4o`, `gpt-4o-mini` |
| Anthropic (OpenAI proxy) | `https://api.anthropic.com` | `claude-3-5-sonnet-20241022` |
| Google Gemini (OpenAI compat) | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` |
| Ollama (로컬) | `http://localhost:11434` | `llama3.2`, `qwen2.5` |
| LM Studio (로컬) | `http://localhost:1234` | 로드한 모델명 |
| OpenRouter | `https://openrouter.ai/api` | `openai/gpt-4o` |

---

## 라이선스

MIT
