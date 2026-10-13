# PROJECT_STATE.md
# AI Guardian — Phase 0 Repository Inspection Results
# Date: 2026-09-18
# Status: OBSERVED FACTS ONLY — no assumptions

---

## 1. Workspace

| Item | Observed Value |
|------|----------------|
| Workspace root | `C:\Users\dk-32\OneDrive\Desktop\Guardian` |
| Files in workspace | 1 |
| Subdirectories | 0 |
| Existing source code | None |
| Existing configuration | None |
| Existing virtual environment | None |
| Existing tests | None |

### Existing Files

| File | Size | Notes |
|------|------|-------|
| `GUARDIAN_CONSTITUTION_v0.1.md` | 7,350 bytes | Primary governing specification |

---

## 2. Version Control

| Item | Observed Value |
|------|----------------|
| Git installed | **NO** — `git` command not found in PATH |
| Git repository initialized | **NO** |
| Existing commits | None |
| `.gitignore` | None |

> **NOTE**: Git must be installed and initialized before version-controlled development begins.

---

## 3. Python Environment

| Item | Observed Value |
|------|----------------|
| Python version | **3.14.2** (CPython, 64-bit, MSC v.1944) |
| Python executable | `C:\Python314\python.exe` |
| `python3` alias | NOT available — only `python` works |
| `py` launcher | Available (maps to Python 3.14.2) |
| pip version | **26.0.1** |
| pip path | `C:\Users\dk-32\AppData\Roaming\Python\Python314\site-packages\pip` |
| `venv` module | Available (`python -m venv`) |
| Virtual environment active | **NO** — none detected |

---

## 4. Hardware (Observed)

| Component | Observed Value |
|-----------|----------------|
| CPU | AMD Ryzen 7 7435HS |
| CPU Cores | 8 physical / 16 logical |
| CPU Base Clock | 3100 MHz |
| RAM | **16 GB** DDR5 (confirmed via `Win32_PhysicalMemory`) |
| GPU | NVIDIA GeForce RTX 3050 Laptop GPU |
| GPU VRAM Total | 4096 MiB (4 GB) |
| GPU VRAM Currently Used | 882 MiB (desktop/apps at inspection time) |
| GPU Driver Version | 610.74 |
| CUDA UMD Version | 13.3 |
| NPU | **NOT DETECTED** |

---

## 5. CUDA / GPU Tooling

| Item | Observed Value |
|------|----------------|
| nvidia-smi | Available — confirmed working |
| PyTorch CUDA | **NOT ENABLED** — CPU-only build (`torch 2.10.0+cpu`) |
| `torch.cuda.is_available()` | **False** |
| CUDA version in torch | **None** |
| USE_CUDA in torch build | 0 — CPU-only confirmed |

IMPORTANT: The GPU hardware exists with CUDA 13.3 drivers but PyTorch is CPU-only.
GPU inference is NOT currently possible from Python.

---

## 6. Installed Python Packages (Relevant Subset)

### Already Present

| Package | Version | Relevance |
|---------|---------|-----------|
| torch | 2.10.0 (CPU-only) | ML framework |
| transformers | 5.1.0 | HuggingFace models |
| pydantic | 2.12.5 | Data validation |
| pydantic-settings | 2.12.0 | Configuration |
| typer | 0.21.1 | CLI framework |
| rich | 15.0.0 | Terminal UI |
| pytest | 9.0.2 | Test framework |
| PyYAML | 6.0.3 | YAML config |
| python-dotenv | 1.2.1 | Env var management |
| groq | 0.37.1 | Groq API client |
| google-genai | 2.8.0 | Google Gemini API |
| langchain | 1.3.4 | LLM framework |
| langgraph | 1.2.4 | Agent orchestration |
| fastapi | 0.128.0 | Web API framework |
| sqlite3 | stdlib | Built-in database |
| chromadb | 1.5.9 | Vector database |
| sentence-transformers | 5.5.1 | Local embeddings |
| numpy | 2.3.5 | Numerical computing |
| psutil | 7.2.2 | System information |
| cryptography | 46.0.3 | Crypto operations |
| python-json-logger | 4.0.0 | Structured logging |
| playwright | 1.60.0 | Browser automation |
| opencv-python | 4.13.0.92 | Computer vision |
| huggingface_hub | 1.4.1 | HF model downloads |
| accelerate | 1.12.0 | HF acceleration |
| onnxruntime | 1.26.0 | ONNX inference |
| neo4j | 5.16.0 | Graph DB client |
| redis | 7.1.0 | Redis client |

### Notable Absences

| Package | Status |
|---------|--------|
| ollama | NOT FOUND |
| llama_cpp | NOT FOUND |
| openai | NOT FOUND |
| anthropic | NOT FOUND |

---

## 7. Other Runtimes / Tools

| Tool | Observed Value |
|------|----------------|
| Node.js | v22.22.0 |
| npm | 10.9.4 |
| Docker CLI | 29.2.0 (daemon NOT running) |
| Git | NOT IN PATH |
| Java | Eclipse Adoptium JDK 25 |
| Go | Available |
| .NET | Available |
| Chocolatey | Available |
| VS Code | Available |

---

## 8. Existing Guardian Project State

ALL = NONE. No source code, config, tests, CLI, venv, requirements.txt, pyproject.toml, or .env file exists yet.

Also detected: `hylexcrypt 2050.2.1` — editable install from a separate personal project.
Guardian must not interfere with it.

---

## 9. Critical Observations

1. Python 3.14.2 is very new. Package compatibility is a RISK.
2. PyTorch is CPU-only despite GPU hardware being present.
3. Git is NOT installed — version control cannot start yet.
4. No virtual environment exists — global env has 100+ packages.
5. Groq API + Google GenAI SDK already installed (API keys not checked).
6. Ollama NOT installed.

---

## 10. Unverified Items

- UNVERIFIED: CUDA-enabled PyTorch compatibility with Python 3.14
- UNVERIFIED: Ollama system application presence (only PATH checked)
- UNVERIFIED: API keys configured in environment
- UNVERIFIED: bitsandbytes functionality without CUDA PyTorch
- UNVERIFIED: Python 3.14 compatibility of all packages
- UNVERIFIED: Docker Desktop operational status
- UNVERIFIED: Disk space for models

---
Generated by Phase 0 inspection — 2026-09-18
All data observed from actual system commands — no assumptions made
