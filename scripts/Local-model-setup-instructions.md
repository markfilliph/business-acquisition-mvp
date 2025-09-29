# Local LLM Lead Generation Setup Guide

## System Requirements

- **RAM:** Minimum 8GB, recommended 16GB
- **Storage:** 10-15GB for models
- **Python:** 3.8+

## Installation Steps

### 1. Install Ollama

```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download/windows
```

### 2. Pull Required Models

```bash
# Main LLM (choose based on your hardware)
ollama pull mistral:latest       # 7B model, ~4.1GB
# OR for better accuracy
ollama pull mistral-small:latest  # 24B model, ~13GB

# Embedding model for RAG
ollama pull nomic-embed-text:latest  # ~274MB
```

### 3. Create Python Environment

```bash
cd business-acquisition-mvp
python -m venv venv_local
source venv_local/bin/activate  # Windows: venv_local\Scripts\activate
```

### 4. Install Dependencies

Create `requirements-local.txt`:

```txt
# Core Dependencies
ollama==0.1.8
pydantic==2.6.0
pandas==2.0.3
requests==2.31.0

# Web Scraping
selenium==4.15.0
beautifulsoup4==4.12.2
playwright==1.40.0
playwright-stealth==1.0.6

# RAG & Vector DB
chromadb==0.4.22
langchain==0.1.0
langchain-community==0.0.10
langchain-ollama==0.0.1

# Data Processing
openpyxl==3.1.2
python-dotenv==1.0.0

# Optional: For better structured outputs
instructor==0.4.0
jsonschema==4.20.0
```

Install:
```bash
pip install -r requirements-local.txt
playwright install chromium  # For web scraping
```

## Configuration

### 1. Create `.env` file:

```env
# Ollama Settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral:latest
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Validation Settings
MIN_EFFECTIVENESS_SCORE=0.7
LEAD_COUNT_MIN=40
LEAD_COUNT_MAX=50

# Data Sources
HAMILTON_BUSINESS_DATA=./data/hamilton_businesses.csv
VERIFIED_SOURCES=./data/verified_sources.json

# Output
OUTPUT_DIR=./output
LOG_LEVEL=INFO
```

### 2. Directory Structure:

```
business-acquisition-mvp/
├── venv_local/
├── data/
│   ├── hamilton_businesses.csv     # Initial business data
│   ├── verified_sources.json       # Verified business info
│   └── raw_scraped/                # Raw scraped data
├── chroma_db/                      # Vector database
├── output/
│   ├── validated_leads/
│   └── enriched_leads/
├── scripts/
│   ├── local_lead_generator.py     # Main generator
│   ├── rag_validator.py            # RAG validation
│   └── data_scraper.py             # Web scraping
└── logs/
```

## Usage

### 1. Basic Lead Generation:

```python
from scripts.local_lead_generator import LocalLLMLeadGenerator

# Initialize
generator = LocalLLMLeadGenerator(model_name="mistral:latest")

# Generate leads
raw_data = [...]  # Your scraped data
lead_batch = generator.generate_leads_with_retry(raw_data)

# Export
df = generator.export_to_sheets_format(lead_batch)
df.to_csv("output/leads.csv")
```

### 2. With RAG Validation:

```python
from scripts.rag_validator import RAGLeadValidator

# Initialize validator
validator = RAGLeadValidator()

# Load knowledge base (once)
sources = [
    {'type': 'csv', 'path': 'data/hamilton_businesses.csv'},
    {'type': 'web', 'url': 'https://www.hamilton.ca/directory'}
]
validator.load_business_data_sources(sources)

# Validate leads
validated_df = validator.batch_validate(leads, confidence_threshold=0.7)
```

### 3. Full Pipeline:

```bash
# Run complete pipeline
python scripts/run_pipeline.py \
    --source "hamilton" \
    --count 45 \
    --min-effectiveness 0.7 \
    --validate \
    --enrich
```

## Performance Optimization

### 1. Model Selection by Hardware:

| RAM | Recommended Model | Performance |
|-----|------------------|-------------|
| 8GB | mistral:7b | Good for basic tasks |
| 16GB | mistral-small:24b | Better accuracy |
| 32GB+ | mixtral:8x7b | Best results |

### 2. Context Window Settings:

```python
# Adjust based on RAM
options = {
    "num_ctx": 4096,   # 8GB RAM
    # "num_ctx": 8192,  # 16GB RAM
    # "num_ctx": 16384, # 32GB+ RAM
}
```

### 3. Batch Processing:

```python
# Process in smaller batches for limited RAM
BATCH_SIZE = 10  # Adjust based on system
for i in range(0, len(leads), BATCH_SIZE):
    batch = leads[i:i+BATCH_SIZE]
    process_batch(batch)
```

## Monitoring & Debugging

### 1. Enable Detailed Logging:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/lead_generation.log'),
        logging.StreamHandler()
    ]
)
```

### 2. Validation Metrics:

```python
# Track validation performance
metrics = {
    'total_processed': 0,
    'hallucinations_caught': 0,
    'effectiveness_failures': 0,
    'data_quality_issues': 0
}
```

### 3. Health Checks:

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test model
ollama run mistral:latest "Test prompt"

# Check ChromaDB
python -c "import chromadb; print(chromadb.__version__)"
```

## Troubleshooting

### Issue: Model running slowly
- Reduce context window size
- Use smaller model (7B instead of 13B+)
- Enable GPU acceleration if available

### Issue: Hallucinations still occurring
- Lower temperature to 0.1 or 0.0
- Increase RAG validation threshold
- Add more verified data sources

### Issue: Not getting 40-50 leads
- Increase initial data pool (scrape 80+ businesses)
- Adjust retry logic
- Check effectiveness scoring

### Issue: Memory errors
- Process in smaller batches
- Use smaller embedding model
- Clear ChromaDB cache periodically

## Integration with Existing Pipeline

Replace Claude API calls in your existing scripts:

```python
# Old (Claude)
# response = claude_client.complete(prompt)

# New (Ollama)
from ollama import Client
client = Client()
response = client.generate(
    model='mistral:latest',
    prompt=prompt,
    options={'temperature': 0.1}
)
```

## Cost Comparison

| Solution | Monthly Cost | Pros | Cons |
|----------|-------------|------|------|
| Claude API | $50-200 | Easy setup | Hallucinations, API limits |
| Local Ollama | $0 | Full control, No limits | Requires setup, Hardware dependent |

## Next Steps

1. **Start Simple:** Test with mistral:7b on sample data
2. **Build Knowledge Base:** Add verified business sources
3. **Iterate:** Refine prompts based on results
4. **Scale:** Move to larger models as needed

## Support Resources

- [Ollama Documentation](https://github.com/ollama/ollama)
- [LangChain RAG Guide](https://python.langchain.com/docs/tutorials/rag/)
- [Pydantic Validation](https://docs.pydantic.dev/)
- [ChromaDB Guide](https://docs.trychroma.com/)
