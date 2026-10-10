#!/usr/bin/env python
# coding: utf-8

# # 🧲 Module 4: Grounding and Hallucination Control
# ## AWS Bedrock Guardrails — Keeping AI Anchored to Your Documents
# 
# ---
# 
# > **Course**: AWS Guardrails — Scratch to Advanced  
# > **Module**: 4  
# > **Primary API**: `converse` inline (grounding only works with real model calls)
# 
# 

# ![image.png](attachment:image.png)

# ---
# ## 🧲 Section 1: The Grounding Score — How It Works
# 
# Grounding **only works with inline guardrails** (converse/invoke_model) — not with `apply_guardrail` standalone.
# 

# ![image.png](attachment:image.png)

# In[1]:


# ─────────────────────────────────────────────────────────────
#  Setup
# ─────────────────────────────────────────────────────────────

import sys
get_ipython().system('"{sys.executable}" -m pip install boto3 botocore --quiet')

import boto3
import botocore
import json

AWS_REGION = "us-east-1"
MODEL_ID   = "amazon.nova-lite-v1:0"

bedrock         = boto3.client("bedrock",         region_name=AWS_REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)

print(f"boto3  : {boto3.__version__}")
print(f"Region : {AWS_REGION}")
print("\n✅ Ready.")


# In[2]:


# ─────────────────────────────────────────────────────────────
#  Create the Grounding Guardrail
#
#  threshold is a float 0.0 – 1.0
#  We start at 0.75 (recommended production value)
# ─────────────────────────────────────────────────────────────

GROUNDING_THRESHOLD = 0.75
RELEVANCE_THRESHOLD = 0.75

def create_or_get_guardrail(name, **kwargs):
    try:
        resp = bedrock.create_guardrail(name=name, **kwargs)
        print(f"✅ Created  : {name}  (ID: {resp['guardrailId']})")
        return resp["guardrailId"], resp["version"]
    except bedrock.exceptions.ConflictException:
        guardrails = bedrock.list_guardrails()["guardrails"]
        existing = next((g for g in guardrails if g["name"] == name), None)
        if existing:
            gid = existing["guardrailId"]
            bedrock.update_guardrail(guardrailIdentifier=gid, name=name, **kwargs)
            print(f"🔄 Updated  : {name}  (ID: {gid})")
            return gid, "DRAFT"
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        return None, None


GROUNDING_GUARDRAIL_ID, _ = create_or_get_guardrail(
    name="mod4-grounding-guardrail",
    description="Grounding and hallucination control — Module 4.",

    blockedInputMessaging=(
        "I can only answer questions based on the provided document."
    ),
    blockedOutputsMessaging=(
        "I could not verify this response against the source document. "
        "This may contain information not present in your provided material. "
        "Please ask about something explicitly mentioned in the document."
    ),

    contextualGroundingPolicyConfig={
        "filtersConfig": [
            {
                "type": "GROUNDING",
                "threshold": GROUNDING_THRESHOLD
            },
            {
                "type": "RELEVANCE",
                "threshold": RELEVANCE_THRESHOLD
            }
        ]
    }
)

print(f"\n   Guardrail ID        : {GROUNDING_GUARDRAIL_ID}")
print(f"   Grounding threshold : {GROUNDING_THRESHOLD}")
print(f"   Relevance threshold : {RELEVANCE_THRESHOLD}")


# ---
# ## 🕳️ Section 2: The Demo Setup — A Fake Document
# 
# We'll use a fictional company document to demonstrate hallucination.
# 
# ### The Source Document Contains:
# - Company name, founded date, location
# - Employee count
# - Main product name
# - CEO name
# - Primary market
# 
# ### The Source Document Does NOT Contain:
# - Revenue figures ← model will hallucinate this
# - Customer count ← model will hallucinate this
# - Stock price ← model will hallucinate this
# - Funding rounds ← model will hallucinate this
# 
# ### How Grounding Will Work
# 
# ```
# Question about info IN document      → grounding score HIGH  → PASSED
# Question about info NOT in document  → model invents answer
#                                        → grounding score LOW → BLOCKED
# ```
# 

# In[3]:


# ─────────────────────────────────────────────────────────────
#  The Source Document and Test Questions
# ─────────────────────────────────────────────────────────────

SOURCE_DOCUMENT = """
NovaTech Solutions — Company Overview (Internal Document)
=========================================================

Company Name   : NovaTech Solutions
Founded        : 2019
Headquarters   : Austin, Texas, USA
Employees      : 245 (as of September 2024)
CEO            : Jennifer Walsh
Primary Market : Healthcare sector
Main Product   : CloudSync — a secure file synchronization platform
                 for healthcare providers.
Latest Update  : CloudSync v3.2 was released in August 2024,
                 adding HIPAA-compliant audit logs.

Mission: To simplify data management for healthcare organisations
while maintaining the highest standards of security and compliance.
"""

# Questions where the answer IS in the document → should PASS
GROUNDED_QUESTIONS = [
    "When was NovaTech Solutions founded?",
    "Who is the CEO of NovaTech Solutions?",
    "What is NovaTech's main product?",
    "How many employees does NovaTech have?",
]

# Questions where the answer is NOT in the document → model will hallucinate → should BLOCK
HALLUCINATION_QUESTIONS = [
    "What was NovaTech's revenue in Q3 2024?",
    "How many customers does NovaTech Solutions have?",
    "What is NovaTech's stock ticker symbol?",
    "How much funding has NovaTech raised?",
]

print("Source document loaded.")
print(f"Grounded questions  : {len(GROUNDED_QUESTIONS)}")
print(f"Hallucination traps : {len(HALLUCINATION_QUESTIONS)}")


# In[4]:


# ─────────────────────────────────────────────────────────────
#  DEMO 1: WITHOUT Grounding Guardrail
#
#  System prompt gives the model permission to answer freely
#  using its general knowledge. This causes it to invent
#  specific numbers for questions not in the document.
# ─────────────────────────────────────────────────────────────

# ── Permissive prompt: model fills gaps with invented details ──
SYSTEM_PROMPT = (
    "You are a helpful business analyst assistant. "
    "Use the provided company information as context and answer all questions "
    "confidently with specific numbers and details."
)

# ── Hallucination questions updated to expect specific numbers ──
HALLUCINATION_QUESTIONS = [
    "What was NovaTech's total annual revenue for 2023?",
    "How many enterprise customers does NovaTech currently serve?",
    "What is NovaTech's current company valuation?",
    "How much funding has NovaTech raised in total across all rounds?",
]

def ask_without_guardrail(question, source_doc):
    """Call the model with no grounding check."""
    response = bedrock_runtime.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{
            "role": "user",
            "content": [{
                "text": (
                    f"Here is some background on NovaTech:\n{source_doc}\n\n"
                    f"Based on this and your knowledge, answer: {question}"
                )
            }]
        }],
        inferenceConfig={"maxTokens": 150}
    )
    return response["output"]["message"]["content"][0]["text"]


print("=" * 65)
print(" WITHOUT GUARDRAIL — Model Invents Specific Answers")
print("=" * 65)
print()

print("── Questions the document CAN answer ──")
for q in GROUNDED_QUESTIONS[:2]:
    ans = ask_without_guardrail(q, SOURCE_DOCUMENT)
    print(f"Q: {q}")
    print(f"A: {ans}")
    print()

print("── Questions NOT in document — watch the model fabricate ──")
for q in HALLUCINATION_QUESTIONS:
    ans = ask_without_guardrail(q, SOURCE_DOCUMENT)
    print(f"Q: {q}")
    print(f"A: {ans}")
    print()


# In[5]:


# ─────────────────────────────────────────────────────────────
#  DEMO 2: WITH Grounding Guardrail
#
#  Same questions, same model, same document.
#  Now the guardrail checks the response before returning it.
#
#  Key: we pass the source document using guardContent with
#  qualifiers=["grounding_source"] so AWS knows what to check against.
# ─────────────────────────────────────────────────────────────

def ask_with_grounding(question, source_doc, guardrail_id, version="DRAFT"):
    """Call the model with grounding guardrail inline."""
    response = bedrock_runtime.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{
            "role": "user",
            "content": [
                # Mark source document as grounding reference
                {
                    "guardContent": {
                        "text": {
                            "text": source_doc,
                            "qualifiers": ["grounding_source"]
                        }
                    }
                },
                # Mark user question as the query
                {
                    "guardContent": {
                        "text": {
                            "text": question,
                            "qualifiers": ["query"]
                        }
                    }
                },
                # Actual message text
                {"text": question}
            ]
        }],
        guardrailConfig={
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion": version,
            "trace": "enabled"
        },
        inferenceConfig={"maxTokens": 150}
    )
    return response


def print_grounding_result(question, response):
    """Print a clean result showing stop reason and response text."""
    stop_reason = response["stopReason"]
    text        = response["output"]["message"]["content"][0]["text"]
    blocked     = stop_reason == "guardrail_intervened"
    icon        = "🚫 BLOCKED" if blocked else "✅ PASSED "

    print(f"{icon}  Q: {question}")
    print(f"         A: {text[:130]}" + ("..." if len(text) > 130 else ""))
    print()


print("=" * 65)
print(" WITH GROUNDING GUARDRAIL")
print("=" * 65)
print()

print("── Grounded questions (answer IS in document) ──")
for q in GROUNDED_QUESTIONS:
    resp = ask_with_grounding(q, SOURCE_DOCUMENT, GROUNDING_GUARDRAIL_ID)
    print_grounding_result(q, resp)

print()
print("── Hallucination traps (answer NOT in document) ──")
for q in HALLUCINATION_QUESTIONS:
    resp = ask_with_grounding(q, SOURCE_DOCUMENT, GROUNDING_GUARDRAIL_ID)
    print_grounding_result(q, resp)


# ---
# ## 📈 Section 3: Threshold Tuning
# 
# The threshold determines how strict the grounding check is. There's a real trade-off:
# 
# ```
# LOW threshold (0.3):                    HIGH threshold (0.9):
# ✅ Fewer false positives                ✅ Catches more hallucinations
# ❌ More hallucinations slip through     ❌ May block valid paraphrased answers
# ```
# 
# ### The Paraphrasing Problem
# 
# A model might paraphrase the document accurately but in different words. High thresholds can block these even though they're correct:
# 
# ```
# Document: "NovaTech was founded in 2019"
# Response: "NovaTech has been operating since 2019" ← correct paraphrase
# 
# Threshold 0.9 → might BLOCK (not exact enough)
# Threshold 0.7 → PASSES (close enough)
# ```
# 
# ### Recommended Thresholds by Use Case
# 
# | Use Case | Grounding | Relevance |
# |---|---|---|
# | Legal/medical documents (high stakes) | `0.80` | `0.80` |
# | General enterprise RAG | `0.75` | `0.70` |
# | Internal knowledge base | `0.70` | `0.65` |
# | Creative/summarization tasks | `0.50` | `0.60` |
# 

# ---
# ## 📄 Section 4: Grounding in RAG Architectures
# 

# ![image.png](attachment:image.png)

# ![image.png](attachment:image.png)

# In[9]:


KNOWLEDGE_BASE = [
    {
        "id": "doc1",
        "content": "NovaTech Solutions was founded in 2019 in Austin, Texas. The CEO is Jennifer Walsh."
    },
    {
        "id": "doc2",
        "content": "NovaTech's main product is CloudSync, a HIPAA-compliant file synchronization platform for healthcare providers. CloudSync v3.2 was released in August 2024."
    },
    {
        "id": "doc3",
        "content": "NovaTech employs 245 people as of September 2024 and primarily serves the healthcare sector."
    },
]


def retrieve_documents(query, knowledge_base, top_k=2):
    query_words = query.lower().split()
    scored = []
    for doc in knowledge_base:
        score = sum(1 for w in query_words if w in doc["content"].lower())
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def rag_query(question, guardrail_id):
    retrieved = retrieve_documents(question, KNOWLEDGE_BASE)
    context   = "\n".join(f"[Doc {i+1}]: {d['content']}" for i, d in enumerate(retrieved))

    response = bedrock_runtime.converse(
        modelId=MODEL_ID,
        # ── Permissive prompt — model fills gaps with invented details ──
        system=[{
            "text": (
                "You are a confident business analyst assistant. "
                "Use the provided context and answer all questions with "
                "specific numbers and details."
            )
        }],
        messages=[{
            "role": "user",
            "content": [
                {
                    "guardContent": {
                        "text": {
                            "text": context,
                            "qualifiers": ["grounding_source"]
                        }
                    }
                },
                {
                    "guardContent": {
                        "text": {
                            "text": question,
                            "qualifiers": ["query"]
                        }
                    }
                },
                {
                    "text": (
                        f"Context:\n{context}\n\n"
                        f"give a specific answer to: {question}"
                    )
                }
            ]
        }],
        guardrailConfig={
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion": "DRAFT",
            "trace": "enabled"
        },
        inferenceConfig={"maxTokens": 200}
    )

    stop_reason = response["stopReason"]
    answer      = response["output"]["message"]["content"][0]["text"]
    blocked     = stop_reason == "guardrail_intervened"

    return {
        "question":   question,
        "retrieved":  [d["id"] for d in retrieved],
        "blocked":    blocked,
        "stop_reason": stop_reason,
        "answer":     answer
    }


rag_questions = [
    "Who is the CEO of NovaTech?",
    "What product does NovaTech make?",
    "What was NovaTech's revenue last quarter?",
    "How many employees does NovaTech have?",
    "What is NovaTech's stock price?",
]

print("=" * 70)
print(" RAG PIPELINE — Grounding Guardrail Demo")
print("=" * 70)

for q in rag_questions:
    result = rag_query(q, GROUNDING_GUARDRAIL_ID)
    icon   = "🚫 BLOCKED" if result["blocked"] else "✅ PASSED "
    print()
    print(icon)
    print(f"Question   : {result['question']}")
    print(f"Retrieved  : {result['retrieved']}")
    print(f"StopReason : {result['stop_reason']}")
    print(f"Answer     : {result['answer'][:150]}" + ("..." if len(result["answer"]) > 150 else ""))
    print("-" * 70)


# ---
# ## 📈 Section 5: Reading the Grounding Trace
# 
# When `trace: "enabled"` is set, the response includes detailed scoring information.
# 
# ### Trace Structure for Grounding
# 
# Unlike content filters (which appear in `inputAssessment`), grounding results appear in **`outputAssessments`** — because grounding evaluates the model's OUTPUT.
# 
# ```json
# {
#   "trace": {
#     "guardrail": {
#       "outputAssessments": {
#         "guardrail-id": [{
#           "contextualGroundingPolicy": {
#             "filters": [
#               {
#                 "type": "GROUNDING",
#                 "threshold": 0.75,
#                 "score": 0.12,      ← actual grounding score
#                 "action": "BLOCKED" ← score < threshold → blocked
#               },
#               {
#                 "type": "RELEVANCE",
#                 "threshold": 0.75,
#                 "score": 0.89,      ← relevance was fine
#                 "action": "NONE"
#               }
#             ]
#           }
#         }]
#       }
#     }
#   }
# }
# ```
# 
# ### What Each Field Tells You
# 
# | Field | Meaning |
# |---|---|
# | `score` | How grounded/relevant the response is (0.0–1.0) |
# | `threshold` | The threshold you configured |
# | `action` | `BLOCKED` if score < threshold, else `NONE` |
# 
# The `score` is your key diagnostic. If you're getting too many false blocks, increase the threshold. Too many hallucinations passing? Decrease it.
# 

# In[10]:


# ─────────────────────────────────────────────────────────────
#  Read the Full Grounding Trace
#  Shows groundingScore and relevanceScore for each response.
# ─────────────────────────────────────────────────────────────

def read_grounding_trace(question, source_doc, guardrail_id):
    """Run a question and show the full grounding trace."""

    response = ask_with_grounding(question, source_doc, guardrail_id)

    stop_reason = response["stopReason"]
    answer      = response["output"]["message"]["content"][0]["text"]
    blocked     = stop_reason == "guardrail_intervened"

    print("─" * 65)
    print(f"Question  : {question}")
    print(f"Decision  : {'🚫 BLOCKED' if blocked else '✅ PASSED'}")
    print(f"Answer    : {answer[:100]}" + ("..." if len(answer) > 100 else ""))

    # Extract grounding scores from trace
    trace      = response.get("trace", {})
    guardrail_trace = trace.get("guardrail", {})
    output_assessments = guardrail_trace.get("outputAssessments", {})

    for gid, assessments in output_assessments.items():
        for assessment in assessments:
            grounding_policy = assessment.get("contextualGroundingPolicy", {})
            filters = grounding_policy.get("filters", [])

            if filters:
                print()
                print(f"  {'Filter':<12} {'Score':<10} {'Threshold':<12} {'Action'}")
                print(f"  {'─'*12} {'─'*10} {'─'*12} {'─'*10}")
                for f in filters:
                    score     = f.get("score", "N/A")
                    threshold = f.get("threshold", "N/A")
                    action    = f.get("action", "N/A")
                    ftype     = f.get("type", "N/A")
                    flag      = "🔴" if action == "BLOCKED" else "🟢"
                    score_str = f"{score:.3f}" if isinstance(score, float) else str(score)
                    print(f"  {flag} {ftype:<12} {score_str:<10} {str(threshold):<12} {action}")
    print()


trace_tests = [
    "Who is the CEO of NovaTech Solutions?",     # grounded — should pass
    "What was NovaTech's revenue in Q3 2024?",   # hallucination — should block
    "How many employees does NovaTech have?",    # grounded — should pass
    "What is NovaTech's stock ticker?",          # hallucination — should block
]

print("=" * 65)
print(" FULL GROUNDING TRACE — Score + Threshold + Action")
print("=" * 65)
print()

for q in trace_tests:
    read_grounding_trace(q, SOURCE_DOCUMENT, GROUNDING_GUARDRAIL_ID)



# In[ ]:




