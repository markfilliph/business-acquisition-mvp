#!/usr/bin/env python3
"""
RAG-Based Lead Validation System - Complete Implementation
Fully implements specifications from Local-model-setup-instructions.md
Prevents hallucination through document-grounded generation
"""

import os
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from langchain_community.document_loaders import WebBaseLoader, CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
import json
import logging
from datetime import datetime
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import time
import traceback
import requests

# Load environment variables
load_dotenv('.env.local')

# Configure logging as per specifications
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/lead_validation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

class RAGLeadValidator:
    """
    RAG system for validating leads against real data sources
    Prevents hallucination by grounding responses in retrieved documents
    Implements all specifications from Local-model-setup-instructions.md
    """

    def __init__(self,
                 collection_name: str = "hamilton_businesses",
                 model_name: str = None,
                 embedding_model: str = None):

        # Load configuration from environment
        self.model_name = model_name or os.getenv('OLLAMA_MODEL', 'mistral:latest')
        self.embedding_model = embedding_model or os.getenv('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text')
        self.collection_name = collection_name
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.min_effectiveness = float(os.getenv('MIN_EFFECTIVENESS_SCORE', '0.7'))
        self.lead_count_min = int(os.getenv('LEAD_COUNT_MIN', '40'))
        self.lead_count_max = int(os.getenv('LEAD_COUNT_MAX', '50'))

        # Initialize validation metrics as per setup instructions
        self.metrics = {
            'total_processed': 0,
            'hallucinations_caught': 0,
            'effectiveness_failures': 0,
            'data_quality_issues': 0
        }

        # Initialize ChromaDB for vector storage
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")

        # Initialize embeddings with Ollama host
        self.embeddings = OllamaEmbeddings(
            model=self.embedding_model,
            base_url=self.ollama_host
        )

        # Initialize collection
        self.setup_collection()

        # Initialize LLM with configurable context window
        context_size = self._get_context_size()
        self.llm = Ollama(
            model=self.model_name,
            base_url=self.ollama_host,
            temperature=0.1,  # Low temp for factual responses
            num_ctx=context_size
        )

        logger.info(f"Initialized RAG validator with model: {self.model_name}")
        logger.info(f"Context window: {context_size}, Embedding model: {self.embedding_model}")
        logger.info(f"Host: {self.ollama_host}")

    def _get_context_size(self) -> int:
        """
        Determine context window size based on available memory
        As per setup instructions
        """
        try:
            import psutil
            memory_gb = psutil.virtual_memory().total / (1024**3)

            if memory_gb >= 32:
                return 16384  # 32GB+ RAM
            elif memory_gb >= 16:
                return 8192   # 16GB RAM
            else:
                return 4096   # 8GB RAM
        except:
            return 4096  # Default for limited systems

    def health_check(self) -> Dict[str, bool]:
        """
        Perform health checks as specified in setup instructions
        """
        checks = {
            'ollama_running': False,
            'model_available': False,
            'chromadb_accessible': False,
            'embedding_model_ready': False
        }

        try:
            # Check Ollama
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            checks['ollama_running'] = response.status_code == 200

            # Check if our model is available
            if checks['ollama_running']:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                checks['model_available'] = self.model_name in model_names
                checks['embedding_model_ready'] = self.embedding_model in model_names

            # Check ChromaDB
            try:
                self.collection.count()
                checks['chromadb_accessible'] = True
            except:
                checks['chromadb_accessible'] = False

        except Exception as e:
            logger.error(f"Health check failed: {e}")

        return checks

    def setup_collection(self):
        """Setup or get ChromaDB collection"""
        try:
            self.collection = self.chroma_client.get_collection(
                name=self.collection_name
            )
            logger.info(f"Using existing collection: {self.collection_name}")
        except:
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Hamilton business data"}
            )
            logger.info(f"Created new collection: {self.collection_name}")

    def _validate_lead_with_retry(self, lead: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Validate lead with retry logic as per setup instructions
        """
        for attempt in range(max_retries):
            try:
                result = self.validate_lead(lead)

                # Check if result is valid
                if result and 'confidence' in result:
                    return result
                else:
                    self.metrics['data_quality_issues'] += 1
                    if attempt < max_retries - 1:
                        logger.warning(f"Validation attempt {attempt + 1} failed for {lead.get('business_name')}, retrying...")
                        time.sleep(1)  # Wait before retry

            except Exception as e:
                logger.error(f"Validation error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # Final fallback result
                    return {
                        "is_valid": False,
                        "confidence": 0.0,
                        "evidence": f"Validation failed after {max_retries} attempts",
                        "issues": [f"Retry exhausted: {str(e)}"],
                        "recommendation": "needs_review",
                        "lead_id": lead.get('business_name', 'unknown'),
                        "validated_at": datetime.now().isoformat(),
                        "sources_checked": 0
                    }

        # This shouldn't be reached, but just in case
        return {
            "is_valid": False,
            "confidence": 0.0,
            "evidence": "Unknown validation failure",
            "issues": ["Validation method failed unexpectedly"],
            "recommendation": "needs_review"
        }

    def load_business_data_sources(self, sources: List[Dict[str, str]]):
        """
        Load and index business data from various sources
        Sources should be dict with 'type' and 'path/url'
        """
        documents = []

        for source in sources:
            if source['type'] == 'csv':
                documents.extend(self._load_csv(source['path']))
            elif source['type'] == 'web':
                documents.extend(self._load_web(source['url']))
            elif source['type'] == 'json':
                documents.extend(self._load_json(source['path']))

        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )

        chunks = []
        for doc in documents:
            split_docs = text_splitter.split_text(doc['content'])
            for chunk in split_docs:
                chunks.append({
                    'content': chunk,
                    'metadata': doc.get('metadata', {})
                })

        # Generate embeddings and store in ChromaDB
        logger.info(f"Indexing {len(chunks)} document chunks...")

        # Process in batches to avoid memory issues
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}")

            for j, chunk in enumerate(batch):
                # Generate embedding
                embedding = self.embeddings.embed_query(chunk['content'])

                # Store in ChromaDB
                self.collection.add(
                    embeddings=[embedding],
                    documents=[chunk['content']],
                    metadatas=[chunk['metadata']],
                    ids=[f"doc_{i+j}_{datetime.now().timestamp()}"]
                )

        logger.info(f"Successfully indexed {len(chunks)} chunks")

    def _load_csv(self, path: str) -> List[Dict]:
        """Load business data from CSV"""
        documents = []
        df = pd.read_csv(path)

        for _, row in df.iterrows():
            content = f"""
            Business: {row.get('name', 'Unknown')}
            Address: {row.get('address', '')}, Hamilton, ON
            Industry: {row.get('industry', '')}
            Years in Business: {row.get('years', '')}
            Revenue: {row.get('revenue', '')}
            Employees: {row.get('employees', '')}
            Website: {row.get('website', '')}
            """

            documents.append({
                'content': content,
                'metadata': {
                    'source': path,
                    'type': 'csv',
                    'business_name': row.get('name', 'Unknown')
                }
            })

        return documents

    def _load_web(self, url: str) -> List[Dict]:
        """Load business data from web pages"""
        try:
            loader = WebBaseLoader(url)
            pages = loader.load()

            documents = []
            for page in pages:
                documents.append({
                    'content': page.page_content,
                    'metadata': {
                        'source': url,
                        'type': 'web'
                    }
                })

            return documents
        except Exception as e:
            logger.error(f"Error loading web data: {e}")
            return []

    def _load_json(self, path: str) -> List[Dict]:
        """Load business data from JSON"""
        documents = []

        with open(path, 'r') as f:
            data = json.load(f)

        for item in data:
            content = json.dumps(item, indent=2)
            documents.append({
                'content': content,
                'metadata': {
                    'source': path,
                    'type': 'json'
                }
            })

        return documents

    def validate_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single lead against the knowledge base
        Returns validation result with evidence
        """

        # Create query from lead information
        query = f"""
        Verify the following business information:
        Name: {lead.get('business_name')}
        Address: {lead.get('address')}
        Industry: {lead.get('industry')}
        Revenue: {lead.get('estimated_revenue')}
        Years in Business: {lead.get('years_in_business')}

        Is this a real business in Hamilton, ON?
        Does it meet these criteria:
        - Revenue between $1-2M
        - Operating for 15+ years
        - Single location only
        """

        # Search for relevant documents
        query_embedding = self.embeddings.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )

        # Build context from retrieved documents
        context = "\\n\\n".join(results['documents'][0])

        # Create validation prompt
        validation_prompt = f"""
        Based ONLY on the following verified information, validate this business lead.

        VERIFIED INFORMATION:
        {context}

        LEAD TO VALIDATE:
        {json.dumps(lead, indent=2)}

        RESPOND WITH JSON:
        {{
            "is_valid": true/false,
            "confidence": 0.0-1.0,
            "evidence": "specific facts from verified information",
            "issues": ["list of any problems found"],
            "recommendation": "accept/reject/needs_review"
        }}

        IMPORTANT: Only use information from the VERIFIED INFORMATION section.
        Do not make up or assume any information not explicitly stated.
        """

        try:
            response = self.llm.invoke(validation_prompt)

            # Parse JSON response
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0]

            validation_result = json.loads(response)

            # Add metadata
            validation_result['lead_id'] = lead.get('business_name', 'unknown')
            validation_result['validated_at'] = datetime.now().isoformat()
            validation_result['sources_checked'] = len(results['documents'][0])

            return validation_result

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                "is_valid": False,
                "confidence": 0.0,
                "evidence": "Validation failed",
                "issues": [str(e)],
                "recommendation": "needs_review"
            }

    def batch_validate(self, leads: List[Dict[str, Any]],
                      confidence_threshold: float = 0.7,
                      batch_size: int = 10) -> pd.DataFrame:
        """
        Validate multiple leads with batch processing and retry logic
        As per setup instructions for memory optimization
        """
        validation_results = []

        # Process in batches to avoid memory issues
        total_batches = (len(leads) + batch_size - 1) // batch_size
        logger.info(f"Processing {len(leads)} leads in {total_batches} batches of size {batch_size}")

        for batch_idx in range(0, len(leads), batch_size):
            batch = leads[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            for i, lead in enumerate(batch, 1):
                global_idx = batch_idx + i
                logger.info(f"Validating lead {global_idx}/{len(leads)}: {lead.get('business_name')}")

                # Implement retry logic
                result = self._validate_lead_with_retry(lead, max_retries=3)

                # Update metrics
                self.metrics['total_processed'] += 1

                # Combine lead data with validation results
                validated_lead = {**lead, **result}

                # Apply confidence threshold
                if result['confidence'] >= confidence_threshold:
                    validated_lead['status'] = 'approved'
                elif result['confidence'] >= 0.5:
                    validated_lead['status'] = 'review'
                else:
                    validated_lead['status'] = 'rejected'
                    self.metrics['effectiveness_failures'] += 1

                # Check for hallucinations
                if not result.get('is_valid', False) and 'hallucination' in str(result.get('issues', [])).lower():
                    self.metrics['hallucinations_caught'] += 1

                validation_results.append(validated_lead)

            # Optional: Clear memory between batches
            if batch_num < total_batches:
                time.sleep(0.1)  # Brief pause between batches

        # Create DataFrame
        df = pd.DataFrame(validation_results)

        # Calculate statistics
        approved = len(df[df['status'] == 'approved'])
        review = len(df[df['status'] == 'review'])
        rejected = len(df[df['status'] == 'rejected'])

        logger.info(f"\\n=== VALIDATION SUMMARY ===")
        logger.info(f"Approved: {approved} ({approved/len(leads)*100:.1f}%)")
        logger.info(f"Needs Review: {review} ({review/len(leads)*100:.1f}%)")
        logger.info(f"Rejected: {rejected} ({rejected/len(leads)*100:.1f}%)")

        # Add metrics tracking as per setup instructions
        logger.info(f"\\n=== PERFORMANCE METRICS ===")
        logger.info(f"Total Processed: {self.metrics['total_processed']}")
        logger.info(f"Hallucinations Caught: {self.metrics['hallucinations_caught']}")
        logger.info(f"Effectiveness Failures: {self.metrics['effectiveness_failures']}")
        logger.info(f"Data Quality Issues: {self.metrics['data_quality_issues']}")

        # Calculate effectiveness rate
        if self.metrics['total_processed'] > 0:
            effectiveness_rate = (self.metrics['total_processed'] - self.metrics['effectiveness_failures']) / self.metrics['total_processed']
            logger.info(f"Effectiveness Rate: {effectiveness_rate:.1%}")

            if effectiveness_rate < self.min_effectiveness:
                logger.warning(f"⚠️  Effectiveness rate {effectiveness_rate:.1%} is below threshold {self.min_effectiveness:.1%}")

        return df

class SmartLeadEnricher:
    """
    Enriches leads with additional data without hallucination
    Uses only verified sources and explicit data
    """

    def __init__(self, rag_validator: RAGLeadValidator):
        self.rag = rag_validator
        self.llm = rag_validator.llm

    def enrich_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich lead with additional verified information
        """

        # Search for additional information
        query = f"Find contact information and details for {lead['business_name']} in Hamilton"

        query_embedding = self.rag.embeddings.embed_query(query)
        results = self.rag.collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )

        context = "\\n".join(results['documents'][0])

        enrichment_prompt = f"""
        Extract ONLY verifiable contact information from the following text.
        Do NOT make up any information. If something is not found, mark it as null.

        BUSINESS: {lead['business_name']}

        SOURCE TEXT:
        {context}

        Return JSON with ONLY information found in the source text:
        {{
            "email": "actual email if found or null",
            "phone": "actual phone if found or null",
            "owner_name": "actual name if found or null",
            "established_year": "actual year if found or null",
            "additional_notes": "any other verified facts"
        }}
        """

        try:
            response = self.llm.invoke(enrichment_prompt)

            if '```json' in response:
                response = response.split('```json')[1].split('```')[0]

            enrichment = json.loads(response)

            # Merge with original lead
            enriched_lead = {**lead}
            for key, value in enrichment.items():
                if value and value != "null":
                    enriched_lead[f"enriched_{key}"] = value

            enriched_lead['enrichment_date'] = datetime.now().isoformat()

            return enriched_lead

        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            return lead

# ============= Usage Example =============

def main():
    """Example usage of RAG validation system"""

    # Initialize RAG validator
    rag = RAGLeadValidator()

    # Perform health check first
    health = rag.health_check()
    logger.info(f"Health check results: {health}")

    if not all(health.values()):
        logger.warning("Some health checks failed. Please verify setup:")
        for check, status in health.items():
            if not status:
                logger.warning(f"  ❌ {check}")

    # Load your data sources
    sources = [
        {'type': 'csv', 'path': 'data/hamilton_businesses.csv'},
        {'type': 'web', 'url': 'https://www.hamilton.ca/business-directory'},
        {'type': 'json', 'path': 'data/verified_leads.json'}
    ]

    # Index the data (only needs to be done once)
    if not Path("./chroma_db").exists():
        logger.info("Building knowledge base...")
        rag.load_business_data_sources(sources)

    # Load leads to validate (from your existing pipeline)
    if Path('leads_to_validate.csv').exists():
        leads_to_validate = pd.read_csv('leads_to_validate.csv').to_dict('records')
    else:
        # Sample data for testing
        leads_to_validate = [
            {
                "business_name": "Hamilton Steel Works",
                "address": "123 Industrial Ave",
                "industry": "Manufacturing",
                "estimated_revenue": 1800000,
                "years_in_business": 29
            }
        ]

    # Validate all leads with batch processing
    validated_df = rag.batch_validate(
        leads_to_validate,
        confidence_threshold=0.7,
        batch_size=10  # Configurable batch size
    )

    # Save validated results
    output_dir = Path(os.getenv('OUTPUT_DIR', './output'))
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f'validated_leads_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    validated_df.to_csv(output_file, index=False)

    # Enrich approved leads
    enricher = SmartLeadEnricher(rag)
    approved_leads = validated_df[validated_df['status'] == 'approved'].to_dict('records')

    enriched_leads = []
    for lead in approved_leads:
        enriched = enricher.enrich_lead(lead)
        enriched_leads.append(enriched)

    # Save enriched leads
    if enriched_leads:
        enriched_df = pd.DataFrame(enriched_leads)
        enriched_file = output_dir / f'enriched_leads_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        enriched_df.to_csv(enriched_file, index=False)

        print(f"\\n✅ Validation and enrichment complete!")
        print(f"📊 {len(validated_df[validated_df['status'] == 'approved'])} leads approved")
        print(f"🔍 {len(enriched_leads)} leads enriched with additional data")
        print(f"💾 Results saved to {output_file}")
        print(f"💾 Enriched data saved to {enriched_file}")
    else:
        print(f"\\n✅ Validation complete!")
        print(f"📊 No leads approved for enrichment")
        print(f"💾 Results saved to {output_file}")

if __name__ == "__main__":
    main()