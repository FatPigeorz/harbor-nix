# Example: Claude Code on SWE-bench

## Prerequisites

- Docker
- Nix (for building closures)
- `pip install datasets swebench`

## Step 1: Build closures

```bash
# Runtime
RUNTIME=$(nix build github:Agentiix/Agentix#runtime --no-link --print-out-paths)

# Agent
AGENT=$(nix build github:Agentiix/Agentix-Agents-Hub#claude-code --no-link --print-out-paths)

# Dataset
DATASET=$(nix build github:Agentiix/Agentix-Datasets#swebench --no-link --print-out-paths)
```

## Step 2: Preprocess dataset

```bash
python Agentix-Datasets/swebench/preprocess.py --output data.jsonl
```

Extract one instance:

```bash
head -1 data.jsonl > instance.json
```

## Step 3: Pull SWE-bench Docker image

```bash
IMAGE=$(python -c "import json; print(json.load(open('instance.json'))['image'])")
docker pull $IMAGE
```

## Step 4: Run

```bash
export ANTHROPIC_API_KEY="sk-ant-..."

python examples/claude-code-swebench/run.py \
    --instance instance.json \
    --runtime-closure $RUNTIME \
    --agent-closure $AGENT \
    --dataset-closure $DATASET \
    --output result.json
```

This creates two sandboxes:

1. **Agent sandbox** — loads claude-code closure, runs agent, collects `git diff`
2. **Eval sandbox** — loads swebench closure, applies patch, runs tests

## Step 5: Check result

```bash
cat result.json | python -m json.tool
```

```json
{
  "instance_id": "django__django-16139",
  "model_patch": "diff --git a/...",
  "verify": {"pass": true, "reason": "All tests passed"},
  "elapsed": 120.5
}
```
