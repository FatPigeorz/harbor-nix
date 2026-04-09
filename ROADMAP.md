# Roadmap

## Phase 0: Agent Evaluation (Current)

Run any agent on any benchmark, collect results.

- [x] Runtime server: /exec, /upload, /download, /health
- [x] Agent adapter protocol: AgentInput → AgentOutput
- [x] Nix closure packaging (binary + adapter)
- [x] Docker deployment with sandbox lifecycle
- [x] SWE-bench Verified runner
- [ ] Run claude-code on SWE-bench Verified end-to-end
- [ ] Add more agents: aider, codex, swe-agent, openhands
- [ ] Add more benchmarks: HumanEval, MBPP, Polyglot

## Phase 1: LLM Proxy

Transparent proxy between agent and LLM API. Captures every token in and out — full trajectory tracing without modifying agent code.

```
Agent binary → LLM Proxy (localhost:9000) → Real LLM API
                    │
                    └── trajectory.jsonl
                        ├── request: model, messages, tools
                        ├── response: content, tool_calls, usage
                        └── timing: latency, ttft
```

**Why:** Most agents are blackbox binaries. We can't instrument their code, but we can intercept their API calls. Set `ANTHROPIC_BASE_URL=http://localhost:9000` and the proxy captures everything.

**Key features:**
- Token-level input/output logging
- Cost tracking (prompt + completion tokens per step)
- Latency profiling (time-to-first-token, total)
- Multi-provider: Anthropic, OpenAI, compatible APIs
- Zero agent modification — just env var override

**Enables:**
- Detailed trajectory collection for RL training data
- Cost analysis across agents and benchmarks
- Debugging agent behavior step-by-step

## Phase 2: Advanced Algorithms — Partial Rollout

Use trajectory data from Phase 1 to enable search and RL algorithms over agent execution traces.

**Partial Rollout:** Instead of running an agent from scratch each time, fork execution at any step and explore alternative continuations.

```
Step 0 → Step 1 → Step 2 → Step 3 (fail)
                      │
                      └──→ Step 2' → Step 3' (success)  ← forked here
```

**Key features:**
- Checkpoint agent state at any step (filesystem + git state)
- Fork sandbox: snapshot → clone → resume with modified context
- Tree search: explore multiple continuations in parallel
- Reward signal: use test results to score branches
- Best-of-N: run N rollouts from a checkpoint, pick the best

**Enables:**
- MCTS / beam search over agent trajectories
- RL fine-tuning with step-level reward signals
- Failure recovery without full restart
- Efficient exploration of solution space
