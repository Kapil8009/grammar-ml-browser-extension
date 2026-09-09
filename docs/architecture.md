# Architecture and extension points

## Runtime flow

1. `extension/content/content.js` reads an editable element or selection.
2. `extension/background.js` sends the request to the configured backend and owns networking, timeout, and optional API-key headers.
3. `backend/app/main.py` validates the API contract, authentication, and request size.
4. `TextPreprocessor` preserves document whitespace, performs NFC normalization, and segments long input for bounded model inference.
5. `CorrectionService` calls only the `CorrectionModel` protocol. It has no dependency on Transformers.
6. `HuggingFaceSeq2SeqModel` lazily loads any compatible encoder-decoder checkpoint with `AutoTokenizer` and `AutoModelForSeq2SeqLM`.
7. `DiffPostprocessor` compares the source with generated output and produces offsets, edit kinds, and user-readable suggestions.
8. The extension shows the model output and applies it only after the user approves it.

## Replace the model

For another Hugging Face seq2seq checkpoint, change `GEC_MODEL_NAME` and `GEC_MODEL_PREFIX`. No API or extension code changes are required.

For a different architecture, implement this interface:

```python
class CorrectionModel(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def loaded(self) -> bool: ...

    def load(self) -> None: ...

    def correct_batch(self, texts: list[str]) -> list[str]: ...
```

Then construct the app with `create_app(settings, model)`. Suitable adapters include:

- GECToR or another edit tagger for lower latency
- ONNX Runtime or OpenVINO for CPU optimization
- a quantized local model
- a private hosted-inference client
- an ensemble or reranker

Keep those details behind the protocol so request schemas, preprocessing, diffs, and the extension remain stable.

## Why diffs happen after correction

Seq2seq models produce corrected text rather than a calibrated list of grammar errors. The postprocessor aligns generated tokens to the source and converts the change into browser-safe spans. It deliberately reports edit operations, not invented grammar categories or confidence scores. A future tagging model can provide richer labels through a compatible postprocessor.

## Production notes

- Pin `GEC_MODEL_REVISION` to a reviewed commit instead of `main`.
- Keep `trust_remote_code=False`; this project does not execute arbitrary Hub model code.
- Keep `GEC_USE_SAFETENSORS=true` unless a trusted checkpoint only provides PyTorch weights; if disabled, pin the reviewed model revision.
- Use HTTPS and a strong `GEC_API_KEY` outside local development.
- Restrict CORS to the published extension origin where possible.
- Run one model copy per process unless memory sizing explicitly allows more.
- Add a request queue, metrics, rate limiting, and structured logs before public multi-user deployment.
- Cache model files on persistent storage to avoid cold-download delays.
