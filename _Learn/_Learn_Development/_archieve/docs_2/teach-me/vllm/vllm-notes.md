# vLLM Core Principles & Performance Tuning Notes

## 1. What is vLLM?
A **high-throughput, low-latency** LLM inference serving framework.
* **Core Goal**: Maximize GPU performance to serve more concurrent requests (Throughput) per card while reducing stuttering (Latency).
* **Summary**: "The Video Memory Management & Scheduling Master" for LLM inference.

---

## 2. Why is vLLM Fast? (Core Principles)

### 2.1 Video Memory Pain Points: KV Cache & Fragmentation
LLM inference is divided into two stages:
1. **Prefill**: Processes the Prompt and generates the first token.
2. **Decode**: Generates subsequent tokens one by one based on previous tokens.
* **KV Cache**: To avoid recomputing Attention for all previous tokens during each Decode, these intermediate results (KV) must be stored in GPU memory.
* **Traditional Framework Pain Points**: Memory is allocated in fixed-length contiguous blocks. If a request finishes using only 50% of its space, the remaining memory cannot be assigned to other requests due to being "non-contiguous," resulting in video memory utilization of only around 20% (**Memory Fragmentation**).

### 2.2 PagedAttention (The "Secret Weapon" of vLLM)
Inspired by **virtual memory paging** in operating systems.
* **Approach**: Instead of allocating a large contiguous block at once, KV Cache is partitioned into fixed-size **Blocks**. Each Block can reside anywhere in memory, mapped via a **Block Table**.
* **Effect**: Idle Blocks can be assigned to new requests at any time. Video memory utilization increases from 20% to 90%+.
* **Benefit**: Completely solves the fragmentation problem, making Continuous Batching possible.

### 2.3 Continuous Batching
* **Static Batching (Traditional)**: Requests in a Batch must run together. Even if 9 requests finish after 10 tokens, they must wait for the 10th request (e.g., 500 tokens) to complete. This leads to massive GPU idle time in later stages.
* **Continuous Batching**: As soon as a request finishes, it is immediately removed from the Batch, and a new request is pulled from the queue to fill the slot. The GPU remains at full load, **exponentially increasing throughput**.

---

## 3. Advanced Performance & Memory Optimization

### 3.1 Quantization
Compresses high-precision weights (e.g., FP16) into lower-precision versions (e.g., INT8, INT4, FP8).
* **Effect**: **Reduces memory footprint (fitting larger models); increases inference speed (low-precision computation is faster)**.
* **AWQ / GPTQ vs Brute-force Precision Reduction**:
    * Models contain a small number of critical weights (**Outliers**). If precision is reduced blindly, this information is lost, and model performance (IQ) plummets.
    * **AWQ and similar algorithms** first detect sensitive weights and apply special protection (retaining higher precision) while compressing the rest. It's about "using the best steel for the blade."

### 3.2 Tensor Parallelism (TP)
When a model is too large for a single GPU (e.g., 70B FP16 requires 140G VRAM, but an A100 has only 80G):
* **Approach**: Splits each layer's weight matrix into N parts (N = Number of GPUs) across cards. In each step, each card computes its part, then intermediate results are exchanged and merged across GPUs via the **NCCL protocol**.
* **Cost**: **Communication bandwidth bottleneck**. If the model is small, communication latency from splitting can offset the speed gains from parallel computation.

### 3.3 Chunked Prefill
* **Background**: In Continuous Batching, a massive Prompt (100k) coming in can block other small requests (stuttering) due to its enormous Prefill computation.
* **Approach**: Splits the Prefill stage of large Prompts into small chunks, interleaved between the Decode stages of smaller requests.
* **Effect**: Significantly reduces **Latency (stuttering)** and lowers **peak video memory usage** for Prefills, allowing for more concurrent requests.

### 3.4 Other Key Optimizations
* **Prefix Caching**: For applications with repeated System Prompts (e.g., a 500-token role setting), previous KV Cache can be reused directly without recomputation.
* **Stream Processing**: Tokens are returned as they are computed instead of waiting for the full response, reducing "Time To First Token" (TTFT).

---

## 4. Practical Parameters (Cheat Sheet)

```bash
# 1. Loading a 70B model with 4x A100-80G
# Use 4-way splitting (TP=4), auto-select precision (usually FP16)
# Max support for 8k context
# Video memory optimization via PagedAttention (on by default)
vllm serve Qwen/Qwen2.5-70B-Instruct \
  --tensor-parallel-size 4 \
  --dtype auto \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.95

# 2. Quantized Loading (Loading 70B with INT4 on a single card)
# (Requires model support for AWQ format files)
vllm serve Qwen/Qwen2.5-70B-Instruct-AWQ \
  --quantization awq
```

| Parameter | Effect | Tuning Suggestion |
|------|------|----------|
| `--tensor-parallel-size N` | Multi-card splitting (TP) | Use for large models (30B+). More cards mean slower communication and higher per-request latency, but higher throughput. |
| `--max-model-len N` | Max context length | **Smaller is better**. Saves memory and allows for larger concurrent batches. Set as needed (e.g., 4096). |
| `--gpu-memory-utilization` | VRAM utilization threshold | Suggest `0.90` or `0.95`. Leave some overhead for Activations to avoid OOM crashes. |
| `--enable-prefix-caching` | Enable Prefix Caching | Recommended for Agentic / Long context scenarios. Greatly reduces computation time for repeated Prompts. |
