from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from backend.training.data import load_parallel_dataset, normalize_target, resolve_dataset_spec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune a Hugging Face seq2seq model for grammatical error correction."
    )
    parser.add_argument("--dataset", default="c4_200m", help="Alias, Hub dataset ID, or local file")
    parser.add_argument("--source-column")
    parser.add_argument("--target-column")
    parser.add_argument("--model-name", default="google/flan-t5-small")
    parser.add_argument("--output-dir", default="models/grammar-corrector")
    parser.add_argument("--prefix", default="Fix grammatical errors in this text: ")
    parser.add_argument("--train-samples", type=int, default=100_000)
    parser.add_argument("--eval-samples", type=int, default=2_000)
    parser.add_argument("--streaming", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-source-length", type=int, default=384)
    parser.add_argument("--max-target-length", type=int, default=384)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=3_000)
    parser.add_argument("--eval-steps", type=int, default=250)
    parser.add_argument("--save-steps", type=int, default=250)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--resume-from-checkpoint")
    parser.add_argument("--push-to-hub", action="store_true")
    parser.add_argument("--hub-model-id")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
            set_seed,
        )
    except ImportError as exc:
        raise SystemExit("Install training dependencies with: pip install -e '.[train]'") from exc

    set_seed(args.seed)
    spec = resolve_dataset_spec(args.dataset, args.source_column, args.target_column)
    train_data, eval_data = load_parallel_dataset(
        spec,
        streaming=args.streaming,
        train_samples=args.train_samples or None,
        eval_samples=args.eval_samples,
        seed=args.seed,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=False)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        args.model_name,
        trust_remote_code=False,
        use_safetensors=True,
    )

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        sources = [f"{args.prefix}{value}" for value in batch[spec.source_column]]
        targets = [normalize_target(value) for value in batch[spec.target_column]]
        model_inputs = tokenizer(
            sources,
            max_length=args.max_source_length,
            truncation=True,
        )
        labels = tokenizer(
            text_target=targets,
            max_length=args.max_target_length,
            truncation=True,
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    remove_columns = train_data.column_names
    train_tokens = train_data.map(tokenize, batched=True, remove_columns=remove_columns)
    eval_tokens = eval_data.map(tokenize, batched=True, remove_columns=eval_data.column_names)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir),
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        eval_strategy="steps",
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=3,
        logging_steps=25,
        predict_with_generate=False,
        fp16=args.fp16,
        bf16=args.bf16,
        gradient_checkpointing=args.gradient_checkpointing,
        report_to="none",
        remove_unused_columns=True,
        push_to_hub=args.push_to_hub,
        hub_model_id=args.hub_model_id,
        seed=args.seed,
    )
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_tokens,
        eval_dataset=eval_tokens,
        processing_class=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model),
    )
    train_result = trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    trainer.save_model()
    tokenizer.save_pretrained(output_dir)
    metrics = {key: float(value) for key, value in train_result.metrics.items()}
    (output_dir / "training_summary.json").write_text(
        json.dumps(
            {
                "base_model": args.model_name,
                "dataset": spec.name,
                "prefix": args.prefix,
                "train_samples": args.train_samples,
                "metrics": metrics,
                "command": " ".join(os.sys.argv),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if args.push_to_hub:
        trainer.push_to_hub()


if __name__ == "__main__":
    main()
