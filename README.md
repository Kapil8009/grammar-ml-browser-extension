# Grammar ML

Grammar ML is a complete, self-hosted English grammatical-error-correction (GEC) system. It combines a Manifest V3 browser extension with a FastAPI backend and a replaceable Hugging Face seq2seq model. The project contains a streaming fine-tuning pipeline for large parallel correction datasets; it does not encode hundreds of grammar rules.

## What is included

- Transformer-based correction through `AutoModelForSeq2SeqLM`
- Lazy model loading and environment-based model replacement
- Sentence-aware preprocessing and model-output postprocessing
- Character offsets and individual edit suggestions generated from the model result
- FastAPI endpoints for single and batch correction, health, readiness, and model metadata
- Optional API-key protection, request-size limits, and extension-compatible CORS
- Chrome/Edge/Brave Manifest V3 extension with popup, in-field action, `Alt+G`, context-menu correction, copy/apply, auto-check, and settings
- A streaming fine-tuning pipeline configured for the 183,894,319-pair C4_200M GEC dataset
- Docker, Docker Compose, Render blueprint, tests, and an extension packaging script

## Architecture

```text
Editable field / selected text / popup
                 │
                 ▼
       Manifest V3 extension
                 │  POST /v1/correct
                 ▼
          FastAPI boundary
                 │
                 ▼
   Unicode + sentence preprocessing
                 │
                 ▼
 CorrectionModel protocol (replaceable)
                 │
         ┌───────┴────────┐
         ▼                ▼
 Hugging Face T5     future GECToR,
 seq2seq engine      ONNX, or hosted model
         │
         ▼
 output validation + token/span diff
         │
         ▼
 corrected text + offset suggestions
                 │
                 ▼
       Browser popup/card/apply
```

See [the detailed architecture](docs/architecture.md) for component boundaries and replacement points.

## Model and dataset decision

The default `jbochi/coedit-small` checkpoint is a 77M-parameter FLAN-T5 derivative. It keeps local CPU deployment practical. Set `GEC_MODEL_NAME=grammarly/coedit-large` and the instruction prefix below for the official 770M-parameter CoEdIT checkpoint when quality matters more than memory and latency.

The free-hosting profile in `render.yaml` uses the smaller MIT-licensed [`visheratin/t5-efficient-tiny-grammar-correction`](https://huggingface.co/visheratin/t5-efficient-tiny-grammar-correction) checkpoint. Its model card says it was fine-tuned on a subset of C4_200M with additional synthetic typos. Local smoke tests peaked at roughly 455 MiB, compared with roughly 599 MiB for CoEdIT-Small, so this is the practical choice for a 512 MiB free service. Switch the environment variables back to CoEdIT-Small on a larger instance for stronger corrections.

CoEdIT is an instruction-tuned text-editing model based on FLAN-T5. The official large checkpoint documents English GEC usage and 770M parameters. Its license is CC BY-NC 4.0, so review the license before commercial use.

The training default is [`martinsr/c4_200m`](https://huggingface.co/datasets/martinsr/c4_200m), a streaming-compatible Parquet conversion of Google's C4_200M synthetic GEC data with 183,894,319 erroneous/correct sentence pairs. For higher final quality, continue fine-tuning on human learner corpora such as W&I+LOCNESS, FCE, Lang-8, NUCLE, and JFLEG, subject to each corpus's license. Synthetic data gives scale; human annotations better represent real errors.

Useful upstream references:

- [C4_200M dataset and streaming usage](https://huggingface.co/datasets/martinsr/c4_200m)
- [Google Research C4_200M source and generation method](https://github.com/google-research-datasets/C4_200M-synthetic-dataset-for-grammatical-error-correction)
- [Official CoEdIT-Large model card](https://huggingface.co/grammarly/coedit-large)
- [CoEdIT paper and source](https://github.com/vipulraheja/coedit)
- [Official GECToR implementation](https://github.com/grammarly/gector), a faster tagging-style alternative
- [BEA-2019 W&I+LOCNESS data and ERRANT evaluation](https://www.cl.cam.ac.uk/research/nl/bea2019st/)

## Run locally

Use Python 3.10–3.13. A virtual environment is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[ml,test]'
cp .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

The first correction downloads the configured model from Hugging Face. Preload it at startup with `GEC_PRELOAD_MODEL=true`.

Verify the API:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/v1/correct \
  -H 'Content-Type: application/json' \
  -d '{"text":"She go to school every day."}'
```

If `GEC_API_KEY` is set, add `-H 'X-API-Key: your-key'` and save the same key in the extension settings.

Docker is an alternative:

```bash
docker compose up --build
```

## Install the extension

1. Start the backend.
2. Open `chrome://extensions` in Chrome, `edge://extensions` in Edge, or the equivalent page in Brave.
3. Enable **Developer mode**.
4. Choose **Load unpacked** and select the `extension` directory.
5. Open the extension settings and test `http://localhost:8000`.
6. Focus a text field and click the purple **G**, press `Alt+G`, or use the popup/context menu.

Package a store-ready ZIP:

```bash
make package-extension
```

The result is written to `outputs/grammar-ml-extension.zip`. Publishing in the Chrome Web Store still requires the owner's developer account, privacy disclosures, screenshots, and store review.

## Deploy the backend

The included `render.yaml` creates a free Docker web service on Render with the compact C4_200M-trained checkpoint. Free services can sleep and the first correction after a cold start can be slow. After deployment:

1. Copy the HTTPS service URL into the extension options.
2. For a private deployment, set `GEC_API_KEY` in Render and copy the same value into the extension options.
3. Restrict `GEC_ALLOWED_ORIGINS` if your extension has a stable published extension ID.

Use at least 2 GB RAM for the default CoEdIT-Small checkpoint in production. The official CoEdIT-Large checkpoint generally needs substantially more memory; benchmark the exact runtime and quantization before sizing production infrastructure.

## Fine-tune a model

Install the training dependencies:

```bash
python -m pip install -e '.[train]'
```

Run a bounded, streaming C4_200M fine-tune:

```bash
python -m backend.training.train \
  --dataset c4_200m \
  --model-name google/flan-t5-small \
  --train-samples 100000 \
  --eval-samples 2000 \
  --max-steps 3000 \
  --output-dir models/grammar-corrector
```

The loader streams the large dataset instead of downloading its roughly 26 GB of Parquet files. Increase samples/steps for real training, use a GPU, and validate on human-authored GEC data. To train from a local CSV, JSON/JSONL, or Parquet file:

```bash
python -m backend.training.train \
  --dataset data/pairs.jsonl \
  --source-column incorrect \
  --target-column corrected \
  --no-streaming
```

Point inference at the result:

```bash
GEC_MODEL_NAME=./models/grammar-corrector \
GEC_MODEL_PREFIX='Fix grammatical errors in this text: ' \
uvicorn backend.app.main:app --port 8000
```

More guidance is in [docs/training.md](docs/training.md).

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `GEC_MODEL_NAME` | `jbochi/coedit-small` | Hugging Face model ID or local checkpoint |
| `GEC_MODEL_PREFIX` | `Fix the grammar: ` | Instruction prepended to every segment |
| `GEC_MODEL_REVISION` | `main` | Hub revision; pin a commit in production |
| `GEC_USE_SAFETENSORS` | `true` | Require safetensors weights; disable only for a reviewed, pinned model |
| `GEC_DEVICE` | `auto` | `auto`, `cpu`, `cuda`, or another PyTorch device |
| `GEC_MAX_INPUT_TOKENS` | `384` | Tokenizer truncation limit per segment |
| `GEC_MAX_NEW_TOKENS` | `256` | Generation output limit |
| `GEC_NUM_BEAMS` | `4` | Beam-search width |
| `GEC_MAX_TEXT_CHARS` | `12000` | API request limit per text |
| `GEC_API_KEY` | empty | Optional shared API key |
| `GEC_ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins |
| `GEC_PRELOAD_MODEL` | `false` | Load the model during startup |

Official CoEdIT-Large settings:

```bash
GEC_MODEL_NAME=grammarly/coedit-large
GEC_MODEL_PREFIX='Fix grammatical errors in this text: '
```

Models trained without instruction prompts may need `GEC_MODEL_PREFIX=''`.

## Test

```bash
python -m pip install -e '.[test]'
pytest
```

The unit and API tests use a fake `CorrectionModel`, so CI does not download a multi-hundred-megabyte checkpoint. A real-model smoke test is intentionally opt-in.

A ready-to-use GitHub Actions definition is provided at
[`docs/github-actions-ci.yml`](docs/github-actions-ci.yml). Copy it to
`.github/workflows/ci.yml` if your GitHub token includes the `workflow` scope.

## Privacy and limitations

Text is transmitted to the backend selected in the extension settings. The extension has no analytics. API keys are kept in local extension storage rather than browser-synced storage. See [PRIVACY.md](PRIVACY.md).

GEC models can make incorrect or meaning-changing edits. Preserve user review and never silently apply changes. Synthetic training data can encode artifacts and does not replace evaluation across dialects, learner levels, names, code, and domain terminology.
