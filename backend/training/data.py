from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    name: str
    source_column: str
    target_column: str
    config: str | None = None


KNOWN_DATASETS: dict[str, DatasetSpec] = {
    "c4_200m": DatasetSpec(
        name="martinsr/c4_200m",
        source_column="input",
        target_column="output",
    ),
    "coedit": DatasetSpec(
        name="grammarly/coedit",
        source_column="src",
        target_column="tgt",
    ),
    "jfleg": DatasetSpec(
        name="jhu-clsp/jfleg",
        source_column="sentence",
        target_column="corrections",
    ),
}


def resolve_dataset_spec(
    dataset: str,
    source_column: str | None = None,
    target_column: str | None = None,
) -> DatasetSpec:
    spec = KNOWN_DATASETS.get(dataset)
    if spec:
        return DatasetSpec(
            name=spec.name,
            source_column=source_column or spec.source_column,
            target_column=target_column or spec.target_column,
            config=spec.config,
        )
    if not source_column or not target_column:
        raise ValueError(
            "Unknown dataset: provide both --source-column and --target-column"
        )
    return DatasetSpec(dataset, source_column, target_column)


def load_parallel_dataset(
    spec: DatasetSpec,
    *,
    streaming: bool,
    train_samples: int | None,
    eval_samples: int,
    seed: int,
) -> tuple[Any, Any]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("Install training dependencies with: pip install -e '.[train]'") from exc

    path = Path(spec.name)
    if path.exists():
        extension = path.suffix.lower().lstrip(".")
        if extension not in {"csv", "json", "jsonl", "parquet"}:
            raise ValueError("Local datasets must be CSV, JSON/JSONL, or Parquet")
        loader = "json" if extension == "jsonl" else extension
        raw = load_dataset(loader, data_files={"train": str(path)}, streaming=streaming)
    else:
        raw = load_dataset(spec.name, spec.config, streaming=streaming)

    if "train" not in raw:
        raise ValueError(f"Dataset {spec.name!r} has no train split")
    train_split = raw["train"]
    columns = set(train_split.column_names or [])
    missing = {spec.source_column, spec.target_column} - columns
    if missing:
        raise ValueError(f"Dataset is missing columns: {', '.join(sorted(missing))}")

    train_split = (
        train_split.shuffle(seed=seed, buffer_size=10_000)
        if streaming
        else train_split.shuffle(seed=seed)
    )
    if train_samples:
        if streaming:
            eval_split = train_split.take(eval_samples)
            train_split = train_split.skip(eval_samples).take(train_samples)
        else:
            count = min(train_samples, max(0, len(train_split) - eval_samples))
            eval_count = min(eval_samples, len(train_split) - count)
            split = train_split.select(range(count + eval_count))
            train_split = split.select(range(count))
            eval_split = split.select(range(count, count + eval_count))
    elif "validation" in raw:
        eval_split = raw["validation"]
    elif streaming:
        eval_split = train_split.take(eval_samples)
        train_split = train_split.skip(eval_samples)
    else:
        split = train_split.train_test_split(test_size=eval_samples, seed=seed)
        train_split, eval_split = split["train"], split["test"]

    return train_split, eval_split


def normalize_target(value: Any) -> str:
    """Some corpora (such as JFLEG) expose several valid corrections."""
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else ""
    return str(value)
