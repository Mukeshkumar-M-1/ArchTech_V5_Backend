# Session: vLLM Inference Optimization
- Level: Beginner (Target: Inference Optimization)
- Started: 2026-04-24
- Status: Mastered

## Concepts
1. ✅ Two Stages of LLM Inference (Prefill vs Decode)
2. ✅ KV Cache
3. ✅ Memory Bottlenecks & Fragmentation
4. ✅ PagedAttention
5. ✅ vLLM Architecture (Scheduler, Worker)
6. ✅ Practical Deployment (--dtype, OpenAI API)
7. ✅ Quantization (AWQ/GPTQ vs Brute-force dtype)
8. ✅ Tensor Parallel (TP, NCCL)
9. ✅ Performance Parameters (--gpu-memory-utilization)
10. ✅ Chunked Prefill

## Misconceptions
- [Chunked Prefill]: Originally thought the main purpose was to reduce video memory.
  - Correction: While it does reduce **peak activation memory**, the core purpose is to reduce **Latency (stuttering)**.

## Log
- Diagnosed: Beginner
- Mastery: Intuitive understanding of memory constraints and fragmentation is strong.
- Final Quiz: 3/3 correct (with minor clarification needed on TP params).
