# Training and evaluation guide

## Recommended data curriculum

A practical high-quality GEC curriculum has two phases:

1. Pre-train or continue fine-tuning on a large synthetic corpus such as C4_200M. This teaches broad edit behavior at scale.
2. Fine-tune at a lower learning rate on human learner data such as W&I+LOCNESS, FCE, Lang-8, NUCLE, and JFLEG. This reduces synthetic-data artifacts and better matches real mistakes.

The C4_200M alias targets `martinsr/c4_200m`, whose Parquet conversion has about 184M `input`/`output` pairs and supports Hugging Face streaming. The project never vendors that dataset in Git.

Review every dataset license and access condition. In particular, the BEA-2019 site describes several learner corpora as non-commercial and requires request forms for Lang-8 and NUCLE.

## Command reference

```bash
python -m backend.training.train --help
```

Important controls:

- `--streaming` avoids a full local download.
- `--train-samples` bounds a shuffled stream for reproducible experiments.
- `--max-steps` is required for predictable streamed training.
- `--gradient-accumulation-steps` increases effective batch size without equal GPU-memory growth.
- `--gradient-checkpointing` reduces activation memory at a compute cost.
- `--fp16` or `--bf16` improves supported GPU throughput; use only one.
- `--resume-from-checkpoint` continues interrupted training.
- `--push-to-hub --hub-model-id owner/name` publishes the trained checkpoint after Hugging Face authentication.

For CoEdIT data, the source already contains editing instructions, so use an empty prefix:

```bash
python -m backend.training.train \
  --dataset coedit \
  --prefix '' \
  --model-name google/flan-t5-small \
  --no-streaming
```

## Evaluation

Training loss alone is not a GEC quality measure. Use a held-out, human-annotated set and report:

- ERRANT span correction precision, recall, and F0.5 on W&I+LOCNESS
- GLEU on JFLEG when fluency-oriented comparison is useful
- latency, memory, and unchanged-text rate
- manual review for meaning preservation, proper nouns, dialects, and domain terms

The BEA-2019 task uses ERRANT and primarily ranks span-correction F0.5, which weights precision twice as strongly as recall. Do not tune on its withheld test set. Keep exact dataset versions, checkpoint revisions, seeds, and generation settings in experiment metadata.

## Moving a trained checkpoint into serving

The training command saves a normal Transformers directory plus `training_summary.json`. Set `GEC_MODEL_NAME` to that local directory or upload it to the Hugging Face Hub. Ensure the serving prefix exactly matches training. The API and browser extension do not need to change.
