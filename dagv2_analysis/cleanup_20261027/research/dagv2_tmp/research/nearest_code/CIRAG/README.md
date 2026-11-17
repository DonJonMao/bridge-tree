# CIRAG
## <a name="quick_start"></a>:flight_departure:Quick Start

1. Environment Setup
  ```bash
  conda create -n cirag python=3.10
  conda activate cirag
  pip install -r requirements.txt 
  ```


2. LLM Servers

  ```bash
  #qwen2.5-7b-instruct
  bash serve_slm.sh
  ```

3. Run

  ```bash
  #qwen2.5-7b-instruct
  python CIRAG.py --dataset 2wikimultihopqa --llm_name qwen2.5-7b-instruct --embedding_name nvidia/NV-Embed-v2

  #qwen-max-2025-01-25
  python CIRAG_API.py --dataset 2wikimultihopqa --llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1 --llm_name qwen-max-2025-01-25 --embedding_name nvidia/NV-Embed-v2
  ```
