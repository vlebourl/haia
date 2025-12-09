# Relevance Scoring Algorithms for Memory Retrieval Systems

Research compiled: 2025-12-09

## Executive Summary

This document presents research on combining cosine similarity scores (from vector embeddings) with extraction confidence scores (from LLM-based memory extraction) for memory retrieval systems. Based on production RAG systems and information retrieval research, we provide mathematical formulations, practical recommendations, and implementation guidelines.

---

## 1. Scoring Strategies: Combining Similarity and Confidence

### 1.1 Multiplicative Approach

**Formula:**
```
final_score = similarity × confidence
```

**Characteristics:**
- Both factors must be high for a high final score
- Naturally handles scale differences (both scores in [0,1])
- No normalization required
- Zero in either factor results in zero final score

**Pros:**
- Simple and intuitive
- Naturally penalizes low confidence or low similarity
- No parameter tuning required
- Avoids normalization artifacts
- Mirrors probabilistic reasoning (joint probability of independent events)

**Cons:**
- Highly conservative (penalizes even moderately low scores heavily)
- May suppress useful memories with moderate confidence
- Difficult to control relative importance of factors
- Can amplify noise if either score is unreliable

**Use Cases:**
- High-precision requirements (prefer accuracy over recall)
- When both similarity and confidence must be high
- Safety-critical applications where false positives are costly

**Example:**
```python
def multiplicative_score(similarity: float, confidence: float) -> float:
    """
    Multiplicative combination: final_score = similarity × confidence

    Args:
        similarity: Cosine similarity [0,1]
        confidence: Extraction confidence [0,1]

    Returns:
        Combined score [0,1]
    """
    return similarity * confidence

# Example: High similarity, moderate confidence
score = multiplicative_score(0.95, 0.60)  # = 0.57
# Example: Moderate both
score = multiplicative_score(0.70, 0.70)  # = 0.49
```

### 1.2 Additive Approach (Weighted Linear Combination)

**Formula:**
```
final_score = α × similarity + β × confidence
where α + β = 1 (normalized weights)
```

**Characteristics:**
- Linear combination of both factors
- Weights control relative importance
- Requires careful weight selection
- Both factors contribute independently

**Pros:**
- Flexible control via weights (α, β)
- Can balance recall vs precision
- Allows one factor to compensate for the other
- Well-understood in information retrieval
- Easy to interpret and tune

**Cons:**
- Requires normalization of input scores
- Weights must be empirically tuned
- Not naturally probabilistic
- May produce high scores even with one very low factor

**Use Cases:**
- When one factor is more important than the other
- Need to balance recall and precision
- Domain expertise suggests specific weight values
- Want explicit control over factor importance

**Common Weight Configurations:**
```python
def additive_score(similarity: float, confidence: float,
                   alpha: float = 0.65, beta: float = 0.35) -> float:
    """
    Additive combination: final_score = α×similarity + β×confidence

    Common configurations:
    - Semantic-focused: α=0.65, β=0.35 (emphasize similarity)
    - Balanced: α=0.50, β=0.50 (equal weight)
    - Confidence-focused: α=0.35, β=0.65 (emphasize confidence)

    Args:
        similarity: Cosine similarity [0,1]
        confidence: Extraction confidence [0,1]
        alpha: Weight for similarity (default: 0.65)
        beta: Weight for confidence (default: 0.35)

    Returns:
        Combined score [0,1]
    """
    assert abs(alpha + beta - 1.0) < 1e-6, "Weights must sum to 1"
    return alpha * similarity + beta * confidence

# Example: High similarity, moderate confidence (semantic-focused)
score = additive_score(0.95, 0.60, alpha=0.65, beta=0.35)  # = 0.828

# Example: Moderate similarity, high confidence (balanced)
score = additive_score(0.70, 0.90, alpha=0.50, beta=0.50)  # = 0.800
```

### 1.3 Hybrid Approach: Reciprocal Rank Fusion (RRF)

**Formula:**
```
RRF_score = Σ [1 / (k + rank_i)]
where rank_i is the rank from each retrieval method, k is a constant (typically 60)
```

**Characteristics:**
- Rank-based fusion (not score-based)
- Robust to score scale differences
- Parameter-free (except k)
- Combines multiple ranked lists

**Pros:**
- No score normalization required
- Robust across different score distributions
- Well-tested in production RAG systems
- Handles multiple retrieval sources elegantly
- Parameter k is stable across domains (60 is standard)

**Cons:**
- Requires ranking (not just scoring)
- Loses information about score magnitudes
- More complex to implement than simple fusion
- Requires separate retrievals/rankings

**Use Cases:**
- Combining results from multiple retrieval methods
- When score scales are incomparable
- Production systems prioritizing robustness
- Multi-stage retrieval pipelines

**Implementation:**
```python
from typing import List, Dict

def reciprocal_rank_fusion(ranked_results: List[List[str]],
                           k: int = 60) -> Dict[str, float]:
    """
    Reciprocal Rank Fusion for combining multiple ranked result lists.

    Standard in production RAG systems (e.g., Elasticsearch, Pinecone).

    Args:
        ranked_results: List of ranked result lists (by similarity, by confidence, etc.)
        k: Constant (typically 60, empirically stable across domains)

    Returns:
        Dictionary mapping document IDs to RRF scores
    """
    rrf_scores = {}

    for result_list in ranked_results:
        for rank, doc_id in enumerate(result_list, start=1):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
            rrf_scores[doc_id] += 1.0 / (k + rank)

    return rrf_scores

# Example: Combine similarity-ranked and confidence-ranked results
similarity_ranked = ["mem_1", "mem_3", "mem_2", "mem_5"]
confidence_ranked = ["mem_2", "mem_1", "mem_4", "mem_3"]

scores = reciprocal_rank_fusion([similarity_ranked, confidence_ranked], k=60)
# mem_1: 1/(60+1) + 1/(60+2) ≈ 0.0328
# mem_2: 1/(60+3) + 1/(60+1) ≈ 0.0323
# mem_3: 1/(60+2) + 1/(60+4) ≈ 0.0318
```

### 1.4 Hybrid Approach: Weighted RRF with Z-Score Normalization

**Formula:**
```
Stage 1 (Within-method fusion): RRF_method = Σ [1 / (k + rank_i)]
Stage 2 (Cross-method fusion): z_score = (score - μ) / σ
Final_score = Σ [w_i × z_score_i]
```

**Characteristics:**
- Two-stage fusion process
- Combines rank-based and score-based methods
- Normalizes scores to comparable scale
- Allows weighted importance

**Pros:**
- Handles heterogeneous retrieval methods
- Robust score normalization via z-scores
- Flexible weighting of different signals
- State-of-the-art in multi-source RAG

**Cons:**
- Most complex implementation
- Requires multiple retrieval stages
- Needs score statistics (mean, std dev)
- Computationally expensive

**Use Cases:**
- Advanced multi-source retrieval systems
- When combining fundamentally different ranking signals
- Enterprise RAG platforms (e.g., Pinecone's HF-RAG)

**Implementation:**
```python
import numpy as np
from typing import List, Dict, Tuple

def weighted_rrf_zscore(
    retrieval_methods: List[Tuple[List[str], List[float], float]],
    k: int = 60
) -> Dict[str, float]:
    """
    Weighted RRF with Z-Score normalization (state-of-the-art fusion).

    Used in production systems like Pinecone HF-RAG.

    Args:
        retrieval_methods: List of (ranked_docs, scores, weight) tuples
        k: RRF constant (default: 60)

    Returns:
        Dictionary mapping document IDs to final weighted scores
    """
    # Stage 1: Within-method RRF scoring
    method_scores = []
    all_doc_ids = set()

    for ranked_docs, _, _ in retrieval_methods:
        rrf_scores = {}
        for rank, doc_id in enumerate(ranked_docs, start=1):
            all_doc_ids.add(doc_id)
            rrf_scores[doc_id] = 1.0 / (k + rank)
        method_scores.append(rrf_scores)

    # Stage 2: Z-score normalization and weighted fusion
    final_scores = {doc_id: 0.0 for doc_id in all_doc_ids}

    for method_idx, (_, _, weight) in enumerate(retrieval_methods):
        scores_list = [method_scores[method_idx].get(doc_id, 0.0)
                       for doc_id in all_doc_ids]

        # Z-score normalization
        mean = np.mean(scores_list)
        std = np.std(scores_list)

        for doc_id in all_doc_ids:
            raw_score = method_scores[method_idx].get(doc_id, 0.0)
            z_score = (raw_score - mean) / std if std > 0 else 0.0
            final_scores[doc_id] += weight * z_score

    return final_scores

# Example usage
methods = [
    (["mem_1", "mem_3", "mem_2"], [0.95, 0.88, 0.82], 0.6),  # Similarity retrieval
    (["mem_2", "mem_1", "mem_4"], [0.92, 0.85, 0.78], 0.4),  # Confidence retrieval
]

scores = weighted_rrf_zscore(methods, k=60)
```

---

## 2. Weighting Methodology: Determining α and β

### 2.1 Domain-Specific Considerations

**For Memory Retrieval Systems:**

1. **Semantic-Focused (α=0.65, β=0.35)**
   - Prioritize relevance to current query
   - Use when: User asks specific questions requiring precise recall
   - Example: "What's my Proxmox VE cluster configuration?"

2. **Balanced (α=0.50, β=0.50)**
   - Equal weight to similarity and confidence
   - Use when: General-purpose retrieval with no strong preference
   - Example: Default configuration for most queries

3. **Confidence-Focused (α=0.35, β=0.65)**
   - Prioritize reliable memories over semantic match
   - Use when: Factual accuracy is critical (decisions, infrastructure details)
   - Example: "What did I decide about backup schedules?"

**Empirical Evidence:**
- Azure AI Search: Uses α≈0.65 for semantic, β≈0.35 for lexical
- Elastic Enterprise Search: Defaults to balanced (0.5/0.5) with user control
- Pinecone: Dynamic weighting based on query classification confidence

### 2.2 User Preference vs Factual Accuracy Tradeoffs

**User Preferences (favor similarity):**
```python
# User asked about preferences → high similarity weight
# Example: "How do I usually configure Docker containers?"
alpha = 0.70  # Emphasize semantic similarity to query
beta = 0.30   # Confidence is secondary
```

**Factual Information (favor confidence):**
```python
# User asked about facts → high confidence weight
# Example: "What's the IP address of my Proxmox node?"
alpha = 0.30  # Similarity is less critical (any mention of the fact)
beta = 0.70   # High confidence ensures accuracy
```

**Adaptive Weighting Based on Memory Category:**
```python
def adaptive_weights(memory_category: str) -> Tuple[float, float]:
    """
    Return (alpha, beta) weights based on memory category.

    Categories from HAIA extraction system:
    - preference: User preferences, conventions, tool choices
    - personal_fact: Personal information, interests
    - technical_context: Infrastructure details, dependencies
    - decision: Architecture decisions with rationale
    - correction: Corrections of prior information
    """
    weights = {
        "preference": (0.70, 0.30),      # Similarity matters most
        "personal_fact": (0.50, 0.50),   # Balanced
        "technical_context": (0.40, 0.60),  # Confidence matters more
        "decision": (0.35, 0.65),        # High confidence for decisions
        "correction": (0.30, 0.70),      # Corrections must be reliable
    }
    return weights.get(memory_category, (0.50, 0.50))  # Default: balanced
```

### 2.3 Empirical Tuning Methods

**Method 1: Grid Search with Human Evaluation**
```python
import itertools
from typing import List, Tuple

def grid_search_weights(
    test_queries: List[str],
    retrieved_memories: List[List[Tuple[str, float, float]]],  # (id, sim, conf)
    human_relevance: List[List[int]],  # Binary relevance judgments
    alpha_range: List[float] = [0.3, 0.4, 0.5, 0.6, 0.7],
    beta_range: List[float] = [0.3, 0.4, 0.5, 0.6, 0.7]
) -> Tuple[float, float]:
    """
    Grid search to find optimal (α, β) weights.

    Args:
        test_queries: List of test queries
        retrieved_memories: Retrieved memories with (id, similarity, confidence)
        human_relevance: Human judgments (1=relevant, 0=not relevant)
        alpha_range: Candidate α values
        beta_range: Candidate β values

    Returns:
        Best (alpha, beta) tuple
    """
    best_ndcg = 0.0
    best_weights = (0.5, 0.5)

    for alpha in alpha_range:
        for beta in beta_range:
            if abs(alpha + beta - 1.0) > 1e-6:
                continue  # Skip invalid weight combinations

            total_ndcg = 0.0
            for query_idx in range(len(test_queries)):
                # Score each memory
                scores = []
                for mem_id, sim, conf in retrieved_memories[query_idx]:
                    score = alpha * sim + beta * conf
                    scores.append((mem_id, score))

                # Sort by score
                scores.sort(key=lambda x: x[1], reverse=True)

                # Calculate NDCG
                ndcg = calculate_ndcg(scores, human_relevance[query_idx])
                total_ndcg += ndcg

            avg_ndcg = total_ndcg / len(test_queries)
            if avg_ndcg > best_ndcg:
                best_ndcg = avg_ndcg
                best_weights = (alpha, beta)

    return best_weights

def calculate_ndcg(ranked_results: List[Tuple[str, float]],
                   relevance: List[int], k: int = 10) -> float:
    """Calculate Normalized Discounted Cumulative Gain @ k"""
    dcg = sum(rel / np.log2(idx + 2)
              for idx, (_, _) in enumerate(ranked_results[:k])
              for rel in [relevance[idx]])

    ideal_relevance = sorted(relevance, reverse=True)
    idcg = sum(rel / np.log2(idx + 2)
               for idx, rel in enumerate(ideal_relevance[:k]))

    return dcg / idcg if idcg > 0 else 0.0
```

**Method 2: A/B Testing with User Feedback**
```python
import random
from dataclasses import dataclass
from typing import Dict

@dataclass
class ABTestConfig:
    variant_a: Tuple[float, float]  # (alpha, beta) for variant A
    variant_b: Tuple[float, float]  # (alpha, beta) for variant B
    sample_ratio: float = 0.5       # 50/50 split

class ABTestScorer:
    """A/B test different weight configurations with user feedback."""

    def __init__(self, config: ABTestConfig):
        self.config = config
        self.feedback: Dict[str, List[int]] = {"A": [], "B": []}

    def score_with_variant(self, similarity: float, confidence: float,
                          user_id: str) -> Tuple[float, str]:
        """
        Score a memory using randomly assigned A/B variant.

        Returns:
            (score, variant) tuple
        """
        # Consistent variant assignment per user (hash-based)
        variant = "A" if hash(user_id) % 100 < (self.config.sample_ratio * 100) else "B"

        alpha, beta = (self.config.variant_a if variant == "A"
                       else self.config.variant_b)

        score = alpha * similarity + beta * confidence
        return score, variant

    def record_feedback(self, variant: str, was_helpful: bool):
        """Record user feedback (thumbs up/down, relevance rating, etc.)"""
        self.feedback[variant].append(1 if was_helpful else 0)

    def analyze_results(self) -> Dict[str, float]:
        """Analyze A/B test results (CTR, satisfaction rate, etc.)"""
        return {
            "A_satisfaction": np.mean(self.feedback["A"]) if self.feedback["A"] else 0.0,
            "B_satisfaction": np.mean(self.feedback["B"]) if self.feedback["B"] else 0.0,
            "A_samples": len(self.feedback["A"]),
            "B_samples": len(self.feedback["B"]),
        }

# Example usage
ab_test = ABTestScorer(ABTestConfig(
    variant_a=(0.65, 0.35),  # Semantic-focused
    variant_b=(0.50, 0.50),  # Balanced
))

score, variant = ab_test.score_with_variant(0.85, 0.70, user_id="user_123")
# User provides feedback...
ab_test.record_feedback(variant, was_helpful=True)

# After collecting data...
results = ab_test.analyze_results()
# {"A_satisfaction": 0.78, "B_satisfaction": 0.82, ...}
```

**Method 3: Dynamic Weighting Based on Query Classification**

Used in Adaptive RAG systems (state-of-the-art).

```python
from enum import Enum

class QueryType(Enum):
    FACTUAL = "factual"           # "What is X?"
    CONCEPTUAL = "conceptual"     # "How does X work?"
    PREFERENCE = "preference"     # "How do I usually X?"

def classify_query(query: str) -> Tuple[QueryType, float]:
    """
    Classify query type using LLM.

    Returns:
        (query_type, confidence) tuple
    """
    # Simplified - in production, use LLM classification
    if "what is" in query.lower() or "what's" in query.lower():
        return QueryType.FACTUAL, 0.92
    elif "how do i usually" in query.lower() or "how do i normally" in query.lower():
        return QueryType.PREFERENCE, 0.88
    else:
        return QueryType.CONCEPTUAL, 0.65

def adaptive_scoring_weights(query: str) -> Tuple[float, float]:
    """
    Dynamically determine weights based on query classification.

    Returns:
        (alpha, beta) weights
    """
    query_type, confidence = classify_query(query)

    if confidence < 0.6:
        # Low confidence → use balanced weights
        return 0.5, 0.5

    if query_type == QueryType.FACTUAL:
        # Factual queries → prioritize confidence
        return 0.35, 0.65
    elif query_type == QueryType.PREFERENCE:
        # Preference queries → prioritize similarity
        return 0.70, 0.30
    else:  # CONCEPTUAL
        # Conceptual queries → balanced
        return 0.55, 0.45

# Example
query = "What's my Proxmox cluster IP address?"
alpha, beta = adaptive_scoring_weights(query)
# Returns: (0.35, 0.65) - factual query, prioritize confidence
```

---

## 3. Threshold Tuning: Similarity and Confidence Thresholds

### 3.1 Common Threshold Ranges

**Cosine Similarity Thresholds:**
- **0.90-0.95**: Conservative deduplication (near-duplicates only)
- **0.80-0.90**: Standard semantic similarity (related content)
- **0.70-0.80**: Broad semantic similarity (loosely related)
- **< 0.70**: Very broad retrieval (risk of irrelevant results)

**Confidence Thresholds:**
- **0.80+**: High-confidence memories only (conservative)
- **0.60-0.80**: Moderate confidence (balanced)
- **0.40-0.60**: Low confidence (aggressive recall)
- **< 0.40**: Experimental/unverified memories

**Empirical Evidence from Production Systems:**
- Azure AI Search: Default similarity threshold = 0.70 for RAG retrieval
- Banking RAG systems: Threshold = 0.70, but found 99% false positive rate (!)
- Job posting deduplication: 0.80 for titles, 0.70 for descriptions
- LLM training data dedup: 0.90+ for conservative deduplication

### 3.2 Methods for Empirical Tuning

**Method 1: Precision-Recall Curve Analysis**
```python
import numpy as np
from sklearn.metrics import precision_recall_curve
import matplotlib.pyplot as plt

def tune_threshold_precision_recall(
    similarities: np.ndarray,
    ground_truth_relevance: np.ndarray,
    target_precision: float = 0.90
) -> float:
    """
    Find optimal similarity threshold using precision-recall curve.

    Args:
        similarities: Cosine similarity scores [0,1]
        ground_truth_relevance: Binary relevance (1=relevant, 0=not)
        target_precision: Desired precision level (e.g., 0.90)

    Returns:
        Optimal similarity threshold
    """
    precision, recall, thresholds = precision_recall_curve(
        ground_truth_relevance, similarities
    )

    # Find threshold that achieves target precision with highest recall
    valid_indices = precision >= target_precision
    if not valid_indices.any():
        return 0.90  # Fallback to conservative threshold

    best_recall_idx = np.argmax(recall[valid_indices])
    optimal_threshold = thresholds[valid_indices][best_recall_idx]

    # Visualization
    plt.figure(figsize=(10, 6))
    plt.plot(recall, precision, label='Precision-Recall Curve')
    plt.axhline(y=target_precision, color='r', linestyle='--',
                label=f'Target Precision={target_precision}')
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Curve for Threshold Tuning')
    plt.legend()
    plt.grid(True)
    plt.savefig('precision_recall_curve.png')

    return optimal_threshold
```

**Method 2: ROC Curve and Optimal Threshold (Youden's J)**
```python
from sklearn.metrics import roc_curve

def tune_threshold_roc(
    similarities: np.ndarray,
    ground_truth_relevance: np.ndarray
) -> float:
    """
    Find optimal threshold using Youden's J statistic from ROC curve.

    Youden's J = Sensitivity + Specificity - 1
    Maximizes the vertical distance from the diagonal (random classifier).

    Args:
        similarities: Cosine similarity scores [0,1]
        ground_truth_relevance: Binary relevance (1=relevant, 0=not)

    Returns:
        Optimal similarity threshold
    """
    fpr, tpr, thresholds = roc_curve(ground_truth_relevance, similarities)

    # Calculate Youden's J statistic
    j_scores = tpr - fpr
    optimal_idx = np.argmax(j_scores)
    optimal_threshold = thresholds[optimal_idx]

    print(f"Optimal threshold: {optimal_threshold:.3f}")
    print(f"TPR (Sensitivity): {tpr[optimal_idx]:.3f}")
    print(f"FPR (1-Specificity): {fpr[optimal_idx]:.3f}")
    print(f"Youden's J: {j_scores[optimal_idx]:.3f}")

    return optimal_threshold
```

**Method 3: Domain-Specific Validation Set**
```python
from typing import List, Tuple

def tune_thresholds_validation_set(
    validation_queries: List[str],
    candidate_memories: List[List[Tuple[str, float, float]]],  # (id, sim, conf)
    ground_truth_relevant: List[List[str]],  # Relevant memory IDs per query
    similarity_range: List[float] = [0.70, 0.75, 0.80, 0.85, 0.90],
    confidence_range: List[float] = [0.40, 0.50, 0.60, 0.70, 0.80]
) -> Tuple[float, float]:
    """
    Tune similarity and confidence thresholds using validation set.

    Optimizes for F1 score (harmonic mean of precision and recall).

    Args:
        validation_queries: Test queries
        candidate_memories: Retrieved memories with (id, similarity, confidence)
        ground_truth_relevant: Ground truth relevant memory IDs
        similarity_range: Candidate similarity thresholds
        confidence_range: Candidate confidence thresholds

    Returns:
        (optimal_similarity_threshold, optimal_confidence_threshold)
    """
    best_f1 = 0.0
    best_thresholds = (0.80, 0.60)  # Default

    for sim_threshold in similarity_range:
        for conf_threshold in confidence_range:
            total_precision = 0.0
            total_recall = 0.0

            for query_idx in range(len(validation_queries)):
                # Filter memories by thresholds
                filtered = [
                    mem_id for mem_id, sim, conf in candidate_memories[query_idx]
                    if sim >= sim_threshold and conf >= conf_threshold
                ]

                # Calculate metrics
                relevant_set = set(ground_truth_relevant[query_idx])
                retrieved_set = set(filtered)

                if not retrieved_set:
                    continue

                true_positives = len(relevant_set & retrieved_set)
                precision = true_positives / len(retrieved_set) if retrieved_set else 0.0
                recall = true_positives / len(relevant_set) if relevant_set else 0.0

                total_precision += precision
                total_recall += recall

            # Calculate average F1
            avg_precision = total_precision / len(validation_queries)
            avg_recall = total_recall / len(validation_queries)
            f1 = (2 * avg_precision * avg_recall / (avg_precision + avg_recall)
                  if (avg_precision + avg_recall) > 0 else 0.0)

            if f1 > best_f1:
                best_f1 = f1
                best_thresholds = (sim_threshold, conf_threshold)

    print(f"Best thresholds: similarity={best_thresholds[0]:.2f}, "
          f"confidence={best_thresholds[1]:.2f}, F1={best_f1:.3f}")

    return best_thresholds
```

### 3.3 A/B Testing Approaches

**Online A/B Testing with User Feedback**
```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

@dataclass
class ThresholdVariant:
    name: str
    similarity_threshold: float
    confidence_threshold: float

@dataclass
class QueryResult:
    timestamp: datetime
    query: str
    memories_retrieved: int
    user_clicked: bool
    user_satisfaction: int  # 1-5 rating

class ThresholdABTest:
    """A/B test different threshold configurations."""

    def __init__(self, variants: List[ThresholdVariant]):
        self.variants = variants
        self.results: Dict[str, List[QueryResult]] = {v.name: [] for v in variants}

    def assign_variant(self, user_id: str) -> ThresholdVariant:
        """Assign user to variant (consistent hashing)."""
        variant_idx = hash(user_id) % len(self.variants)
        return self.variants[variant_idx]

    def record_result(self, variant_name: str, result: QueryResult):
        """Record query result for analysis."""
        self.results[variant_name].append(result)

    def analyze(self, min_days: int = 7) -> Dict[str, Dict[str, float]]:
        """
        Analyze A/B test results after minimum testing period.

        Metrics:
        - CTR (click-through rate): % of queries with user click
        - Avg satisfaction: Average 1-5 rating
        - Avg memories retrieved: Average result count
        - Zero-result rate: % of queries with no results
        """
        cutoff_date = datetime.now() - timedelta(days=min_days)
        analysis = {}

        for variant_name, results in self.results.items():
            # Filter to recent results
            recent = [r for r in results if r.timestamp >= cutoff_date]

            if not recent:
                continue

            ctr = sum(1 for r in recent if r.user_clicked) / len(recent)
            avg_satisfaction = np.mean([r.user_satisfaction for r in recent])
            avg_memories = np.mean([r.memories_retrieved for r in recent])
            zero_result_rate = sum(1 for r in recent if r.memories_retrieved == 0) / len(recent)

            analysis[variant_name] = {
                "ctr": ctr,
                "avg_satisfaction": avg_satisfaction,
                "avg_memories_retrieved": avg_memories,
                "zero_result_rate": zero_result_rate,
                "sample_size": len(recent),
            }

        return analysis

    def recommend_winner(self) -> str:
        """Recommend winning variant based on composite score."""
        analysis = self.analyze()

        # Composite score: 0.4*CTR + 0.4*satisfaction + 0.2*(1-zero_result_rate)
        scores = {}
        for variant_name, metrics in analysis.items():
            score = (0.4 * metrics["ctr"] +
                     0.4 * (metrics["avg_satisfaction"] / 5.0) +
                     0.2 * (1 - metrics["zero_result_rate"]))
            scores[variant_name] = score

        winner = max(scores, key=scores.get)
        print(f"\nRecommended winner: {winner} (score: {scores[winner]:.3f})")
        print(f"Metrics: {analysis[winner]}")

        return winner

# Example usage
variants = [
    ThresholdVariant("conservative", similarity_threshold=0.85, confidence_threshold=0.70),
    ThresholdVariant("balanced", similarity_threshold=0.80, confidence_threshold=0.60),
    ThresholdVariant("aggressive", similarity_threshold=0.75, confidence_threshold=0.50),
]

ab_test = ThresholdABTest(variants)

# Simulate data collection...
# variant = ab_test.assign_variant(user_id="user_123")
# ab_test.record_result(variant.name, QueryResult(...))

# After 7+ days...
# winner = ab_test.recommend_winner()
```

### 3.4 User Feedback Integration

**Explicit Feedback Mechanisms:**
```python
from enum import Enum

class FeedbackType(Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"           # 1-5 stars
    RELEVANCE = "relevance"     # Binary: relevant/not relevant

@dataclass
class MemoryFeedback:
    memory_id: str
    query: str
    similarity: float
    confidence: float
    feedback_type: FeedbackType
    feedback_value: float  # 1.0 for thumbs up, 0.0 for thumbs down, 1-5 for rating
    timestamp: datetime

class FeedbackBasedTuner:
    """Continuously tune thresholds based on user feedback."""

    def __init__(self, initial_similarity_threshold: float = 0.80,
                 initial_confidence_threshold: float = 0.60):
        self.similarity_threshold = initial_similarity_threshold
        self.confidence_threshold = initial_confidence_threshold
        self.feedback_history: List[MemoryFeedback] = []

    def record_feedback(self, feedback: MemoryFeedback):
        """Record user feedback."""
        self.feedback_history.append(feedback)

    def retune_weekly(self):
        """
        Retune thresholds based on last 7 days of feedback.

        Strategy:
        - If memories below threshold get positive feedback → lower threshold
        - If memories above threshold get negative feedback → raise threshold
        """
        cutoff = datetime.now() - timedelta(days=7)
        recent_feedback = [f for f in self.feedback_history if f.timestamp >= cutoff]

        if len(recent_feedback) < 20:
            print("Insufficient feedback for retuning (need 20+ samples)")
            return

        # Analyze false negatives (good memories below threshold)
        false_negatives = [
            f for f in recent_feedback
            if f.similarity < self.similarity_threshold
            and f.feedback_value >= 0.7  # Positive feedback
        ]

        # Analyze false positives (bad memories above threshold)
        false_positives = [
            f for f in recent_feedback
            if f.similarity >= self.similarity_threshold
            and f.feedback_value < 0.3  # Negative feedback
        ]

        # Adjust thresholds
        fn_rate = len(false_negatives) / len(recent_feedback)
        fp_rate = len(false_positives) / len(recent_feedback)

        if fn_rate > 0.15:  # Too many false negatives
            self.similarity_threshold *= 0.95  # Lower by 5%
            print(f"Lowering similarity threshold to {self.similarity_threshold:.3f} "
                  f"(FN rate: {fn_rate:.2%})")

        if fp_rate > 0.10:  # Too many false positives
            self.similarity_threshold *= 1.05  # Raise by 5%
            print(f"Raising similarity threshold to {self.similarity_threshold:.3f} "
                  f"(FP rate: {fp_rate:.2%})")

        # Similar logic for confidence threshold...
```

---

## 4. Deduplication Strategies

### 4.1 Similarity Thresholds for Deduplication

**Recommended Thresholds:**
- **0.95-0.99**: Near-exact duplicates (minor phrasing differences)
- **0.90-0.95**: Semantic duplicates (same meaning, different wording)
- **0.85-0.90**: Highly similar (overlapping but distinct information)
- **< 0.85**: Not considered duplicates

**Empirical Evidence:**
- Job posting dedup: 0.80 for titles (accounts for phrasing differences)
- LLM training data: 0.90+ for conservative deduplication
- Economic research papers: 0.85-0.90 for title deduplication
- Feature request dedup: 0.80-0.85 for semantic deduplication

### 4.2 When to Deduplicate

**Triggers for Deduplication:**
1. **New memory extraction**: Before storing, check if similar memory exists
2. **Periodic batch dedup**: Weekly/monthly cleanup of historical memories
3. **On retrieval**: Deduplicate results before presenting to user
4. **On memory update**: When updating a memory, merge with duplicates

**Decision Framework:**
```python
from enum import Enum

class DeduplicationStrategy(Enum):
    KEEP_HIGHEST_CONFIDENCE = "keep_highest_confidence"
    KEEP_MOST_RECENT = "keep_most_recent"
    MERGE_INFORMATION = "merge_information"
    KEEP_BOTH = "keep_both"

def should_deduplicate(memory1: dict, memory2: dict,
                       similarity: float,
                       confidence_diff_threshold: float = 0.20) -> bool:
    """
    Decide if two memories should be deduplicated.

    Args:
        memory1, memory2: Memory objects with 'confidence', 'category', 'timestamp'
        similarity: Cosine similarity between embeddings
        confidence_diff_threshold: Max confidence difference to consider merging

    Returns:
        True if memories should be deduplicated
    """
    # Similarity threshold
    if similarity < 0.90:
        return False

    # Same category required
    if memory1["category"] != memory2["category"]:
        return False

    # Large confidence difference → keep both (one might be outdated/incorrect)
    conf_diff = abs(memory1["confidence"] - memory2["confidence"])
    if conf_diff > confidence_diff_threshold:
        # Exception: If one is a correction, always deduplicate
        if memory1["category"] == "correction" or memory2["category"] == "correction":
            return True
        return False

    return True

def deduplicate_memories(memory1: dict, memory2: dict,
                         strategy: DeduplicationStrategy) -> dict:
    """
    Merge two duplicate memories using specified strategy.

    Returns:
        Merged memory object
    """
    if strategy == DeduplicationStrategy.KEEP_HIGHEST_CONFIDENCE:
        return memory1 if memory1["confidence"] > memory2["confidence"] else memory2

    elif strategy == DeduplicationStrategy.KEEP_MOST_RECENT:
        return memory1 if memory1["timestamp"] > memory2["timestamp"] else memory2

    elif strategy == DeduplicationStrategy.MERGE_INFORMATION:
        # Merge content, keep highest confidence, most recent timestamp
        return {
            "content": f"{memory1['content']} | {memory2['content']}",
            "confidence": max(memory1["confidence"], memory2["confidence"]),
            "timestamp": max(memory1["timestamp"], memory2["timestamp"]),
            "category": memory1["category"],
            "mentions": memory1.get("mentions", 1) + memory2.get("mentions", 1),
        }

    else:  # KEEP_BOTH
        return None  # Don't deduplicate
```

### 4.3 Performance Impact of Pairwise Comparison

**Naive Pairwise Comparison:**
- **Complexity**: O(n²) for n memories
- **Practical limit**: ~10,000 memories (100M comparisons)
- **Bottleneck**: Cosine similarity computation + database reads

**Example Performance:**
```python
import time

def naive_deduplication(memories: List[dict],
                       threshold: float = 0.90) -> List[Tuple[int, int]]:
    """
    Naive O(n²) pairwise deduplication.

    Returns:
        List of (index1, index2) duplicate pairs
    """
    start = time.time()
    duplicates = []

    for i in range(len(memories)):
        for j in range(i + 1, len(memories)):
            # Compute cosine similarity (expensive!)
            similarity = cosine_similarity(
                memories[i]["embedding"],
                memories[j]["embedding"]
            )

            if similarity >= threshold:
                duplicates.append((i, j))

    elapsed = time.time() - start
    print(f"Naive dedup: {len(memories)} memories, "
          f"{len(duplicates)} duplicates, {elapsed:.2f}s")

    return duplicates

# Performance estimates:
# 100 memories: ~0.01s (4,950 comparisons)
# 1,000 memories: ~1s (499,500 comparisons)
# 10,000 memories: ~100s (49,995,000 comparisons) ← impractical!
```

### 4.4 Efficient Algorithms: LSH and Clustering

**Locality-Sensitive Hashing (LSH) - Recommended Approach**

LSH reduces deduplication from O(n²) to approximately O(n) by hashing similar embeddings to the same buckets.

**How LSH Works:**
1. **MinHash signatures**: Convert high-dimensional embeddings to compact fingerprints
2. **Banding technique**: Divide signatures into bands of rows
3. **Bucketing**: Hash each band; documents in same bucket are candidate duplicates
4. **Candidate verification**: Only compute exact similarity for candidates

**Implementation:**
```python
from datasketch import MinHash, MinHashLSH
from typing import List, Set

class LSHDeduplicator:
    """
    Efficient deduplication using MinHash LSH.

    Reduces complexity from O(n²) to approximately O(n).
    """

    def __init__(self, threshold: float = 0.90, num_perm: int = 128):
        """
        Args:
            threshold: Jaccard similarity threshold (maps to cosine similarity)
            num_perm: Number of permutations (higher = more accurate, slower)
        """
        self.threshold = threshold
        self.num_perm = num_perm
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)

    def add_memory(self, memory_id: str, text: str):
        """Add memory to LSH index."""
        minhash = self._text_to_minhash(text)
        self.lsh.insert(memory_id, minhash)

    def find_duplicates(self, memory_id: str, text: str) -> Set[str]:
        """
        Find duplicate memories using LSH.

        Returns:
            Set of duplicate memory IDs
        """
        minhash = self._text_to_minhash(text)
        # LSH returns candidates; optionally verify with exact similarity
        candidates = self.lsh.query(minhash)
        return set(candidates)

    def _text_to_minhash(self, text: str, shingle_size: int = 3) -> MinHash:
        """Convert text to MinHash signature using character shingles."""
        minhash = MinHash(num_perm=self.num_perm)

        # Create character shingles (n-grams)
        shingles = [text[i:i+shingle_size]
                    for i in range(len(text) - shingle_size + 1)]

        for shingle in shingles:
            minhash.update(shingle.encode('utf8'))

        return minhash

# Example usage
lsh_dedup = LSHDeduplicator(threshold=0.90, num_perm=128)

memories = [
    ("mem_1", "Proxmox cluster uses Ceph for storage"),
    ("mem_2", "The Proxmox cluster utilizes Ceph for storage"),  # Near-duplicate
    ("mem_3", "Home Assistant controls ESPHome devices"),
]

# Index memories
for mem_id, text in memories:
    lsh_dedup.add_memory(mem_id, text)

# Find duplicates for new memory
duplicates = lsh_dedup.find_duplicates("mem_new", "Proxmox cluster has Ceph storage")
# Returns: {"mem_1", "mem_2"}

# Performance: O(n) insertion, O(1) query (amortized)
```

**Parameter Tuning for LSH:**
```python
def tune_lsh_parameters(threshold: float) -> Tuple[int, int]:
    """
    Calculate optimal LSH parameters (bands, rows) for given threshold.

    Relationship: threshold ≈ (1/bands)^(1/rows)

    Args:
        threshold: Desired Jaccard similarity threshold (0.85-0.95)

    Returns:
        (num_bands, rows_per_band) tuple
    """
    # Common configurations
    configs = [
        (20, 5, 0.87),   # 20 bands × 5 rows = 100 permutations, ~0.87 threshold
        (25, 5, 0.85),   # 25 bands × 5 rows = 125 permutations, ~0.85 threshold
        (16, 8, 0.90),   # 16 bands × 8 rows = 128 permutations, ~0.90 threshold
        (10, 10, 0.92),  # 10 bands × 10 rows = 100 permutations, ~0.92 threshold
    ]

    # Find closest match
    best_config = min(configs, key=lambda x: abs(x[2] - threshold))
    num_bands, rows_per_band, actual_threshold = best_config

    print(f"For threshold={threshold:.2f}, use:")
    print(f"  Bands: {num_bands}, Rows per band: {rows_per_band}")
    print(f"  Actual threshold: ~{actual_threshold:.2f}")
    print(f"  Total permutations: {num_bands * rows_per_band}")

    return num_bands, rows_per_band

# Example
bands, rows = tune_lsh_parameters(0.90)
# Output: Bands: 16, Rows per band: 8, Actual threshold: ~0.90
```

**Clustering-Based Deduplication (Alternative Approach)**

For smaller datasets (<10K memories), clustering can be simpler than LSH.

```python
from sklearn.cluster import DBSCAN
import numpy as np

def cluster_based_deduplication(
    embeddings: np.ndarray,
    memory_ids: List[str],
    similarity_threshold: float = 0.90,
    min_cluster_size: int = 2
) -> List[List[str]]:
    """
    Deduplicate using DBSCAN clustering.

    Args:
        embeddings: Memory embeddings (n x dim)
        memory_ids: Corresponding memory IDs
        similarity_threshold: Cosine similarity threshold (0.90 = eps 0.1)
        min_cluster_size: Minimum memories to form cluster

    Returns:
        List of duplicate clusters (each cluster is a list of memory IDs)
    """
    # Convert cosine similarity threshold to epsilon (distance)
    # cosine_similarity = 1 - cosine_distance
    # eps = 1 - similarity_threshold
    eps = 1.0 - similarity_threshold

    # DBSCAN with cosine metric
    clustering = DBSCAN(eps=eps, min_samples=min_cluster_size, metric='cosine')
    labels = clustering.fit_predict(embeddings)

    # Group memories by cluster
    clusters = {}
    for mem_id, label in zip(memory_ids, labels):
        if label == -1:  # Noise point (no cluster)
            continue
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(mem_id)

    # Return only clusters with 2+ members (duplicates)
    duplicate_clusters = [cluster for cluster in clusters.values() if len(cluster) >= 2]

    return duplicate_clusters

# Example usage
embeddings = np.array([
    [0.1, 0.2, 0.7],  # mem_1
    [0.15, 0.25, 0.6],  # mem_2 (similar to mem_1)
    [0.9, 0.1, 0.0],  # mem_3 (distinct)
])
memory_ids = ["mem_1", "mem_2", "mem_3"]

duplicate_clusters = cluster_based_deduplication(embeddings, memory_ids, threshold=0.90)
# Returns: [["mem_1", "mem_2"]]
```

**Performance Comparison:**

| Method | Complexity | Best For | Memory Usage |
|--------|-----------|----------|--------------|
| Naive pairwise | O(n²) | < 1K memories | Low |
| LSH (MinHash) | O(n) | 10K-1M+ memories | Medium |
| DBSCAN clustering | O(n log n) | 1K-10K memories | Medium |
| Hierarchical clustering | O(n² log n) | < 5K memories | High |

**Recommendation for HAIA:**
- **< 1,000 memories**: Naive pairwise (simplest, sufficient performance)
- **1,000-10,000 memories**: DBSCAN clustering (good balance)
- **> 10,000 memories**: MinHash LSH (scales best)

---

## 5. Production Examples: Real-World Systems

### 5.1 Azure AI Search (Microsoft)

**Architecture:**
- Hybrid search combining BM25 (lexical) + dense vectors (semantic)
- Reciprocal Rank Fusion (RRF) for score fusion
- Default weights: ~65% semantic, ~35% lexical

**Key Features:**
```python
# Conceptual representation of Azure AI Search scoring

def azure_hybrid_search(query: str,
                       semantic_weight: float = 0.65,
                       lexical_weight: float = 0.35) -> List[dict]:
    """
    Azure AI Search hybrid retrieval strategy.

    1. Semantic search (dense vectors)
    2. Lexical search (BM25)
    3. RRF fusion with weights
    """
    # Stage 1: Semantic search
    semantic_results = semantic_search(query)  # Returns ranked list

    # Stage 2: Lexical search
    lexical_results = lexical_search(query)   # Returns ranked list

    # Stage 3: RRF fusion
    fused_results = reciprocal_rank_fusion(
        [semantic_results, lexical_results],
        weights=[semantic_weight, lexical_weight],
        k=60
    )

    return fused_results
```

**Lessons:**
- Semantic-focused weight (0.65) works well for most use cases
- RRF is robust and production-proven
- User-configurable weights enable domain adaptation

### 5.2 Pinecone (Vector Database)

**Architecture:**
- Cascading retrieval: Dense → Sparse → Reranking
- Weighted RRF with z-score normalization (HF-RAG)
- Dynamic weighting based on query type

**Key Features:**
```python
# Conceptual representation of Pinecone's cascading retrieval

def pinecone_cascading_retrieval(query: str) -> List[dict]:
    """
    Pinecone cascading retrieval with reranking.

    1. Dense vector search (semantic)
    2. Sparse vector search (lexical)
    3. Weighted RRF fusion
    4. Neural reranking (cross-encoder)
    """
    # Stage 1: Dense retrieval
    dense_results = dense_vector_search(query, top_k=100)

    # Stage 2: Sparse retrieval
    sparse_results = sparse_vector_search(query, top_k=100)

    # Stage 3: RRF fusion
    fused_results = weighted_rrf_zscore(
        [(dense_results, 0.6), (sparse_results, 0.4)]
    )

    # Stage 4: Neural reranking
    reranked_results = cross_encoder_rerank(fused_results, query, top_k=10)

    return reranked_results
```

**Reported Improvements:**
- 48% improvement over standard dense retrieval
- Critical for production RAG applications

### 5.3 Elastic Enterprise Search

**Architecture:**
- BM25, kNN, hybrid search (RRF)
- User-configurable weight balance
- Per-query weight adaptation

**Key Features:**
```python
# Conceptual representation of Elastic hybrid search

def elastic_hybrid_search(query: str,
                         semantic_ratio: float = 0.5) -> List[dict]:
    """
    Elastic Enterprise Search hybrid retrieval.

    Dynamic weighting: user controls semantic vs lexical balance.
    """
    # BM25 lexical search
    bm25_results = bm25_search(query)

    # kNN semantic search
    knn_results = knn_vector_search(query)

    # RRF fusion with dynamic weights
    lexical_weight = 1.0 - semantic_ratio
    semantic_weight = semantic_ratio

    results = reciprocal_rank_fusion(
        [bm25_results, knn_results],
        weights=[lexical_weight, semantic_weight]
    )

    return results
```

**Lessons:**
- Flexible user control improves domain adaptation
- Default 50/50 balance works for general use
- Allows per-query weight adjustment

### 5.4 Confident RAG (Research System)

**Architecture:**
- Multi-embedding generation with confidence scoring
- Selects answer with highest confidence
- Uses self-certainty and distributional perplexity metrics

**Key Features:**
```python
# Conceptual representation of Confident RAG

def confident_rag(query: str, num_samples: int = 5) -> dict:
    """
    Confident RAG: Generate multiple answers, select highest confidence.

    Confidence metrics:
    - Self-certainty: Model's own confidence assessment
    - Distributional perplexity: Consistency across samples
    """
    answers = []

    # Generate multiple answer candidates
    for _ in range(num_samples):
        # Retrieve with slight randomness
        retrieved = retrieve_memories(query, temperature=0.2)

        # Generate answer
        answer = generate_answer(query, retrieved)

        # Compute confidence
        self_certainty = model_self_assess_confidence(answer)
        dist_perplexity = compute_distributional_perplexity(answer, answers)

        combined_confidence = (self_certainty + dist_perplexity) / 2

        answers.append({
            "text": answer,
            "confidence": combined_confidence,
            "retrieved_memories": retrieved,
        })

    # Select highest confidence answer
    best_answer = max(answers, key=lambda x: x["confidence"])

    return best_answer
```

**Reported Improvements:**
- 10-12.4% improvement over baseline RAG
- Effective for mathematics and factual QA

### 5.5 Adaptive RAG (State-of-the-Art)

**Architecture:**
- Query classification (factual vs conceptual)
- Dynamic weight adjustment based on query type
- Confidence-aware retrieval strategy

**Key Features:**
```python
# Conceptual representation of Adaptive RAG

def adaptive_rag(query: str) -> List[dict]:
    """
    Adaptive RAG: Dynamically adjust retrieval strategy per query.

    1. Classify query (factual, conceptual, preference)
    2. Adjust dense/sparse weights based on classification
    3. Retrieve with optimized strategy
    """
    # Stage 1: Classify query
    query_type, classification_confidence = classify_query(query)

    # Stage 2: Determine weights
    if classification_confidence < 0.6:
        # Low confidence → balanced retrieval
        dense_weight, sparse_weight = 0.5, 0.5
    elif query_type == "factual":
        # Factual → emphasize exact matching (sparse)
        dense_weight, sparse_weight = 0.3, 0.7
    elif query_type == "conceptual":
        # Conceptual → emphasize semantic (dense)
        dense_weight, sparse_weight = 0.7, 0.3
    else:  # preference
        # Preference → balanced with slight semantic bias
        dense_weight, sparse_weight = 0.55, 0.45

    # Stage 3: Retrieve
    dense_results = dense_retrieval(query)
    sparse_results = sparse_retrieval(query)

    # Stage 4: Weighted RRF fusion
    results = weighted_rrf(
        [(dense_results, dense_weight), (sparse_results, sparse_weight)]
    )

    return results
```

**Lessons:**
- Query-adaptive strategies outperform static approaches
- Classification confidence is critical for dynamic weighting
- Fallback to balanced weights when uncertain

---

## 6. Recommended Defaults for Memory Retrieval

### 6.1 Scoring Method

**Recommendation: Weighted Additive (α=0.65, β=0.35)**

**Rationale:**
- Memory retrieval typically prioritizes semantic relevance (similarity)
- Confidence serves as a quality filter (prevents low-quality memories)
- Additive approach allows explicit control and easy tuning
- Widely used in production RAG systems (Azure, Elastic)

**Alternative: Multiplicative for high-precision use cases**
- Use when both high similarity AND high confidence are required
- Example: Retrieving infrastructure facts that must be accurate

### 6.2 Threshold Values

**Similarity Threshold: 0.75**
- Balances recall (find relevant memories) and precision (avoid irrelevant)
- Lower than deduplication threshold (0.90) to allow diverse results
- Empirically validated in production RAG systems

**Confidence Threshold: 0.50**
- Matches HAIA's "selective/aggressive" extraction strategy (min_confidence=0.40)
- Slight buffer to filter lower-quality extractions
- Can be lowered to 0.40 if recall is insufficient

### 6.3 Deduplication Threshold

**Deduplication Threshold: 0.92**
- Conservative: Only removes very similar memories
- Preserves distinct information even if semantically close
- Empirically proven for semantic deduplication

**When to Deduplicate:**
- **On insertion**: Check for duplicates before storing new memory
- **Not on retrieval**: Deduplicating at retrieval time is too slow

**Deduplication Strategy:**
- Use MinHash LSH for scalability (if > 1,000 memories)
- Keep highest confidence memory when deduplicating
- Exception: If newer memory is a correction, keep the correction

### 6.4 Sample Configuration

```python
# config.py - Recommended defaults for HAIA memory retrieval

from dataclasses import dataclass

@dataclass
class MemoryRetrievalConfig:
    """Configuration for memory retrieval scoring and deduplication."""

    # Scoring method
    scoring_method: str = "additive"  # "additive" | "multiplicative" | "rrf"

    # Additive weights (used if scoring_method == "additive")
    similarity_weight: float = 0.65  # α
    confidence_weight: float = 0.35  # β

    # Thresholds
    similarity_threshold: float = 0.75
    confidence_threshold: float = 0.50

    # Deduplication
    deduplication_threshold: float = 0.92
    deduplication_strategy: str = "keep_highest_confidence"  # "keep_highest_confidence" | "keep_most_recent" | "merge"

    # Advanced (for RRF)
    rrf_k: int = 60

    # LSH (for deduplication)
    lsh_num_perm: int = 128
    lsh_threshold: float = 0.92

# Usage
config = MemoryRetrievalConfig()

def score_memory(similarity: float, confidence: float,
                 config: MemoryRetrievalConfig) -> float:
    """Score memory using configured method."""
    if config.scoring_method == "additive":
        return (config.similarity_weight * similarity +
                config.confidence_weight * confidence)
    elif config.scoring_method == "multiplicative":
        return similarity * confidence
    else:
        raise ValueError(f"Unknown scoring method: {config.scoring_method}")
```

---

## 7. Implementation Pseudocode

### 7.1 Complete Retrieval Pipeline

```python
from typing import List, Dict, Tuple
import numpy as np

class MemoryRetriever:
    """
    Complete memory retrieval system with scoring and deduplication.
    """

    def __init__(self, config: MemoryRetrievalConfig):
        self.config = config
        self.lsh_deduplicator = LSHDeduplicator(
            threshold=config.deduplication_threshold,
            num_perm=config.lsh_num_perm
        )

    async def retrieve(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Retrieve top-k memories for query.

        Pipeline:
        1. Generate query embedding
        2. Vector similarity search (Neo4j)
        3. Score results (similarity × confidence)
        4. Filter by thresholds
        5. Deduplicate
        6. Rank and return top-k
        """
        # Step 1: Generate query embedding
        query_embedding = await self.generate_embedding(query)

        # Step 2: Vector similarity search
        # Retrieve more than top_k to allow for filtering/deduplication
        candidate_memories = await self.neo4j_vector_search(
            query_embedding,
            top_k=top_k * 3  # 3x buffer
        )

        # Step 3: Score results
        scored_memories = []
        for memory in candidate_memories:
            # Compute final score
            score = self.compute_score(
                memory["similarity"],
                memory["confidence"]
            )

            # Add score to memory
            memory["final_score"] = score
            scored_memories.append(memory)

        # Step 4: Filter by thresholds
        filtered_memories = [
            mem for mem in scored_memories
            if mem["similarity"] >= self.config.similarity_threshold
            and mem["confidence"] >= self.config.confidence_threshold
        ]

        # Step 5: Deduplicate
        deduplicated_memories = self.deduplicate_results(filtered_memories)

        # Step 6: Rank by final score and return top-k
        ranked_memories = sorted(
            deduplicated_memories,
            key=lambda x: x["final_score"],
            reverse=True
        )

        return ranked_memories[:top_k]

    def compute_score(self, similarity: float, confidence: float) -> float:
        """Compute final score using configured method."""
        if self.config.scoring_method == "additive":
            return (self.config.similarity_weight * similarity +
                    self.config.confidence_weight * confidence)
        elif self.config.scoring_method == "multiplicative":
            return similarity * confidence
        else:
            raise ValueError(f"Unknown method: {self.config.scoring_method}")

    def deduplicate_results(self, memories: List[Dict]) -> List[Dict]:
        """
        Deduplicate memories using LSH.

        Strategy: Keep highest confidence memory from each duplicate cluster.
        """
        if len(memories) <= 1:
            return memories

        # Build LSH index
        lsh = LSHDeduplicator(
            threshold=self.config.deduplication_threshold,
            num_perm=self.config.lsh_num_perm
        )

        for memory in memories:
            lsh.add_memory(memory["id"], memory["content"])

        # Find duplicate clusters
        seen = set()
        deduplicated = []

        for memory in memories:
            if memory["id"] in seen:
                continue

            # Find duplicates
            duplicates = lsh.find_duplicates(memory["id"], memory["content"])

            if not duplicates:
                deduplicated.append(memory)
                seen.add(memory["id"])
            else:
                # Get all memories in duplicate cluster
                cluster = [m for m in memories if m["id"] in duplicates]
                cluster.append(memory)

                # Select best memory from cluster
                if self.config.deduplication_strategy == "keep_highest_confidence":
                    best = max(cluster, key=lambda x: x["confidence"])
                elif self.config.deduplication_strategy == "keep_most_recent":
                    best = max(cluster, key=lambda x: x["timestamp"])
                else:  # merge
                    best = self.merge_memories(cluster)

                deduplicated.append(best)
                seen.update(duplicates)
                seen.add(memory["id"])

        return deduplicated

    async def neo4j_vector_search(self, query_embedding: np.ndarray,
                                   top_k: int) -> List[Dict]:
        """
        Perform vector similarity search in Neo4j.

        Cypher query with vector similarity using db.index.vector.queryNodes.
        """
        # Placeholder - actual implementation would use Neo4j driver
        # See HAIA's neo4j.py service for full implementation
        pass

    async def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using configured model (Ollama)."""
        # Placeholder - actual implementation would call Ollama
        pass

    def merge_memories(self, memories: List[Dict]) -> Dict:
        """Merge multiple memories into one (for merge strategy)."""
        return {
            "id": memories[0]["id"],  # Use first ID
            "content": " | ".join(m["content"] for m in memories),
            "confidence": max(m["confidence"] for m in memories),
            "timestamp": max(m["timestamp"] for m in memories),
            "category": memories[0]["category"],
            "mentions": sum(m.get("mentions", 1) for m in memories),
        }

# Usage example
async def main():
    config = MemoryRetrievalConfig()
    retriever = MemoryRetriever(config)

    memories = await retriever.retrieve(
        query="What's my Proxmox cluster configuration?",
        top_k=5
    )

    for memory in memories:
        print(f"[{memory['final_score']:.3f}] {memory['content']}")
        print(f"  Similarity: {memory['similarity']:.3f}, "
              f"Confidence: {memory['confidence']:.3f}")
```

---

## 8. Summary and Recommendations

### 8.1 Quick Reference Table

| Aspect | Recommended Default | Alternative | Use Case |
|--------|---------------------|-------------|----------|
| **Scoring Method** | Additive (α=0.65, β=0.35) | Multiplicative | General memory retrieval |
| **Similarity Weight** | 0.65 | 0.50 (balanced), 0.70 (semantic-focused) | Emphasize query relevance |
| **Confidence Weight** | 0.35 | 0.50 (balanced), 0.65 (fact-focused) | Filter low-quality memories |
| **Similarity Threshold** | 0.75 | 0.80 (conservative), 0.70 (aggressive) | Balance recall/precision |
| **Confidence Threshold** | 0.50 | 0.60 (conservative), 0.40 (aggressive) | Align with extraction strategy |
| **Deduplication Threshold** | 0.92 | 0.90 (aggressive), 0.95 (conservative) | Remove near-duplicates |
| **Deduplication Method** | LSH (MinHash) | DBSCAN clustering | Scalable deduplication |
| **Deduplication Strategy** | Keep highest confidence | Keep most recent, Merge | Choose best from duplicates |

### 8.2 Key Takeaways

1. **Additive scoring (α=0.65, β=0.35) is recommended** for general memory retrieval
   - Semantic similarity (α) is primary signal
   - Confidence (β) acts as quality filter
   - Easy to tune and well-proven in production

2. **Use adaptive weighting for advanced systems**
   - Classify query type (factual, conceptual, preference)
   - Adjust weights dynamically based on query
   - Fallback to balanced weights when uncertain

3. **Threshold tuning requires empirical validation**
   - Start with defaults (similarity=0.75, confidence=0.50)
   - Use precision-recall curves or validation sets
   - A/B test with real users for best results

4. **Deduplication is critical for quality**
   - Use LSH (MinHash) for scalability (> 1,000 memories)
   - Deduplicate on insertion, not retrieval
   - Conservative threshold (0.92) preserves distinct information

5. **Production systems favor robustness over complexity**
   - RRF is widely used for score fusion (parameter-free, robust)
   - Simple additive fusion works well with proper normalization
   - Multiplicative scoring is too conservative for most use cases

### 8.3 Next Steps for HAIA

1. **Implement additive scoring** as default retrieval method
2. **Add adaptive weighting** based on memory category
3. **Integrate LSH deduplication** during memory insertion
4. **Collect user feedback** for threshold tuning (thumbs up/down on retrievals)
5. **A/B test** different weight configurations to optimize for HAIA's use case

---

## Sources

### Scoring Strategies & Hybrid Retrieval
- [Building a Retrieval Augmented Generation (RAG) system from scratch - Part 2](https://learnbybuilding.ai/tutorial/rag-from-scratch-part-2-semantics-and-cosine-similarity/)
- [How Can You Improve RAG Similarity Scores?](https://www.gigaspaces.com/question/how-can-you-improve-rag-similarity-scores-improvement-techniques)
- [COS-Mix: Cosine Similarity and Distance Fusion](https://arxiv.org/html/2406.00638v1)
- [Optimizing RAG with Hybrid Search & Reranking](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking)

### Weighting Methodology
- [Hybrid Search Explained | Weaviate](https://weaviate.io/blog/hybrid-search-explained)
- [Hybrid search scoring (RRF) - Azure AI Search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)
- [Hybrid Search - Azure AI Search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview)
- [Hybrid optimization and ontology-based semantic model](https://link.springer.com/article/10.1007/s11227-022-04708-9)

### Threshold Tuning
- [Quality Assurance for LLM-RAG Systems](https://arxiv.org/html/2502.05782v1)
- [A complete guide to RAG evaluation](https://www.evidentlyai.com/llm-guide/rag-evaluation)
- [Confident-ai LLM Evaluation Metrics](https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation)
- [Testing RAG Applications](https://testfort.com/blog/testing-rag-systems)
- [Reducing False Positives in RAG Semantic Caching](https://www.infoq.com/articles/reducing-false-positives-retrieval-augmented-generation/)

### Confidence Scoring
- [Confident RAG: Multi-Embedding and Confidence Scoring](https://arxiv.org/html/2507.17442)
- [RAG Series – Adaptive RAG, Confidence, Precision & nDCG](https://www.dbi-services.com/blog/rag-series-adaptive-rag-understanding-confidence-precision-ndcg/)
- [RAG Evaluation & Confidence Score](https://medium.com/@naresh.kancharla/rag-evaluation-confidence-score-dfd1bdd01b82)

### Deduplication
- [Near-duplicate Detection with LSH and Datasketch](https://yorko.github.io/2023/practical-near-dup-detection/)
- [MinHash LSH in Milvus](https://milvus.io/blog/minhash-lsh-in-milvus-the-secret-weapon-for-fighting-duplicates-in-llm-training-data.md)
- [Document Deduplication with LSH](https://mattilyra.github.io/2017/05/23/document-deduplication-with-lsh.html)
- [Large-scale Near-deduplication Behind BigCode](https://huggingface.co/blog/dedup)
- [Semantic Deduplication — NeMo-Curator](https://docs.nvidia.com/nemo/curator/latest/curate-text/process-data/deduplication/semdedup.html)

### Production RAG Systems
- [Better RAG results with Reciprocal Rank Fusion](https://www.assembled.com/blog/better-rag-results-with-reciprocal-rank-fusion-and-hybrid-search)
- [HF-RAG: Hierarchical Fusion-based RAG](https://arxiv.org/html/2509.02837)
- [The Best Pre-Built Enterprise RAG Platforms in 2025](https://www.firecrawl.dev/blog/best-enterprise-rag-platforms-2025)
- [Neural-Based Rank Fusion for Multi-Source Retrieval](https://www.rohan-paul.com/p/neural-based-rank-fusion-for-multi)

### Multiplicative vs Additive Scoring
- [Add or Multiply? A Tutorial on Ranking and Choosing with Multiple Criteria](https://www.researchgate.net/publication/275674494_Add_or_Multiply_A_Tutorial_on_Ranking_and_Choosing_with_Multiple_Criteria)
- [Score Normalization - ScienceDirect](https://www.sciencedirect.com/topics/computer-science/score-normalization)
- [Information Retrieval - Fusion in IR](https://ccc.inaoep.mx/~villasen/bib/Hsu-FusionInIR07.pdf)
