#!/bin/bash
# Benchmark qwen2.5vl:3b speed

echo "🚀 Benchmarking qwen2.5vl:3b..."

# Convert image to base64
IMAGE_B64=$(base64 -w 0 accidental-maruti-suzuki-car-scrap-2219421532-ylwl3ab5.jpg)

# Run benchmark
time curl -s http://localhost:11434/api/generate -d "{
  \"model\": \"qwen2.5vl:3b\",
  \"prompt\": \"Extract license plate. JSON: {\\\"plate\\\": \\\"MH12AB1234\\\"}\",
  \"images\": [\"$IMAGE_B64\"],
  \"stream\": false,
  \"options\": {
    \"temperature\": 0.0,
    \"num_gpu\": 999
  }
}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Response: {data.get('response')}\")
print(f\"Total: {data.get('total_duration', 0) / 1e9:.4f}s\")
print(f\"Inference: {data.get('eval_duration', 0) / 1e9:.4f}s\")
"
