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

## 🎨 신규 기능 안내

### 1. Vision (이미지 입력) 지원 🖼️
`LLMApiNode`에 선택적(Optional) 입력 핀인 `image`가 추가되었습니다.
- **사용 방법**: `로드 이미지(Load Image)` 노드 등에서 생성된 `IMAGE` 출력을 `image` 핀에 연결합니다.
- **동작**: 입력된 이미지는 백엔드에서 자동으로 Base64 JPEG 형식으로 인코딩되며, ChatML 템플릿의 마지막 `user` 메시지에 OpenAI 규격(`image_url`)으로 추가되어 전송됩니다. 
- **지원 모델**: `gpt-4o`, `gemini-1.5-pro`, `claude-3-5-sonnet` 등 멀티모달(Vision) 모델을 지정하면 이미지에 대한 질의응답이 가능해집니다.

---

### 2. 프롬프트 템플릿 매니저 노드 📝
ComfyUI 내에서 직접 템플릿 파일을 조회, 편집, 추가, 삭제할 수 있는 `📝 LLM Prompt Template Manager` 노드가 추가되었습니다.
- **액션(action)**:
  - `Read/Select`: `filename`에서 고른 템플릿 파일을 읽어서 `template_content` 출력을 통해 텍스트로 보냅니다.
  - `Save/Create`: 
    - `new_filename`에 파일명(예: `my_prompt.txt`)을 쓰고 실행하면 새 템플릿을 만듭니다.
    - `new_filename`이 비어 있으면, 현재 드롭다운으로 선택된 파일에 `content`에 입력한 텍스트를 덮어씁니다(수정).
  - `Delete`: 선택된 파일을 삭제합니다.
- **연동 팁**: 매니저 노드의 `template_content` 출력을 `Cloud LLM` 노드의 `template_override` 입력 핀에 바로 연결하면, 템플릿 파일을 매니저 노드에서 실시간으로 수정하며 즉시 테스트할 수 있어 개발 속도가 비약적으로 향상됩니다.

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
