#!/usr/bin/env python
# coding: utf-8

# # 🛡️ Module 1: Setting Up Your First AWS Guardrails
# 
# ---
# 
# > **Course**: AWS Guardrails — Scratch to Advanced  
# > **Module**: 1  
# 
# ---
# 
# ### How Guardrails Fit Into the Big Picture
# 
# ```
# Your App  ──► [Guardrail: INPUT check]  ──► Amazon Bedrock (LLM)  ──► [Guardrail: OUTPUT check]  ──► Your App
#                ↓ BLOCK if violates           (Nova, Claude, etc.)      ↓ BLOCK if violates
#            Custom error message                                      Custom error message
# ```
# 
# A guardrail evaluates **both** the user's input AND the model's output. If either violates your policies, the guardrail intercepts and returns your custom safe message instead of the harmful content.
# 
# 

# ![image.png](attachment:image.png)

# 
# ### Why Amazon Nova Lite?
# 
# We use **Amazon Nova Lite** in this course because:
# 
# | Reason | Detail |
# |--------|--------|
# | ✅ No approval form | Amazon's own model — available immediately in your account |
# | ✅ Free to enable | Just click "Enable" in Model Access — no use-case review |
# | ✅ Full guardrail support | Works with all guardrail policies |
# | ✅ Fast & cheap | One of the lowest-cost models on Bedrock (~$0.06/1M input tokens) |
# | ✅ Converse API support | Works with the recommended Converse API |
# 

# ---
# ## 📋 Prerequisites & Checklist
# 
# Before running any cell, work through this checklist:
# 
# ### 1. AWS Account Setup
# - [ ] You have an AWS account (free tier works for this module)
# - [ ] You are signed in to the AWS Console
# 
# 
# ### AWS Credentials
# You need AWS credentials configured. There are three ways:
# 
# ** AWS CLI (Recommended for local dev)**
# ```bash
# pip install awscli
# aws configure
# # Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output (json)
# ```
# 
# 
# > ⚠️ **Never hardcode AWS credentials in notebook cells.** We will use `boto3`'s credential chain, which automatically reads from `~/.aws/credentials` or environment variables.
# 

# ## ⚙️ Step 0: Install & Import Dependencies
# 
# Before anything else, we install and import the three libraries this course runs on:
# 
# | Library | Purpose |
# |---------|---------|
# | `boto3` | The official AWS SDK for Python — how we talk to Amazon Bedrock |
# | `botocore` | The engine underneath boto3 — we import it separately to catch AWS-specific errors |
# | `json` | Bedrock's API sends/receives raw text — we use this to build requests and parse responses |

# In[9]:


import sys

get_ipython().system('"{sys.executable}" -m pip install boto3 botocore --quiet')

import boto3
import botocore
import json


print(f"boto3 version   : {boto3.__version__}")
print(f"botocore version: {botocore.__version__}")
print("\n✅ All dependencies ready.")


# ---
# ## ⚙️ Section 1: boto3 Configuration — Two Clients, Two Purposes
# 
# ** A critical beginner mistake: using the wrong boto3 client. Amazon Bedrock has **two separate API endpoints**, each with its own boto3 client
# 
# 
# 

# ![image.png](attachment:image.png)

# 
# ### Region Selection
# 
# Not all AWS regions support all Bedrock models. As of 2025, the safest choices are:
# 
# | Region | Name | Guardrails Support |
# |--------|------|--------------------|
# | `us-east-1` | US East (N. Virginia) | ✅ Full support |
# | `us-west-2` | US West (Oregon) | ✅ Full support |
# | `eu-west-1` | EU (Ireland) | ✅ Full support |
# | `ap-southeast-1` | Asia Pacific (Singapore) | ✅ Full support |
# 
# We'll use `us-east-1` in this module. Change it to your nearest region if latency matters.

# In[10]:


# ─────────────────────────────────────────────────────────────
#  STEP 2: Configure boto3 Clients
# ─────────────────────────────────────────────────────────────

AWS_REGION = "us-east-1"   

# Control plane: create/manage guardrails
bedrock = boto3.client(
    service_name="bedrock",
    region_name=AWS_REGION
)

# Data plane: invoke models, apply guardrails at runtime
bedrock_runtime = boto3.client(
    service_name="bedrock-runtime",
    region_name=AWS_REGION
)

print(f"Region configured : {AWS_REGION}")
print(f"Control plane URL : {bedrock.meta.endpoint_url}")
print(f"Data plane URL    : {bedrock_runtime.meta.endpoint_url}")
print("\n✅ boto3 clients created successfully.")


# In[11]:


# ─────────────────────────────────────────────────────────────
#  STEP 3: Verify Your Connection & Credentials
#
#  This makes a real API call (list_foundation_models) to confirm:
#   ✓ Your credentials are valid
#   ✓ The region is correct
#   ✓ Bedrock is accessible from your environment
# ─────────────────────────────────────────────────────────────

print("Testing connection to Amazon Bedrock...")
print("-" * 50)

try:
    response = bedrock.list_foundation_models(byOutputModality="TEXT")
    nova_models = [m for m in response["modelSummaries"] if "nova" in m["modelId"].lower()]
    
    print("✅ Connected to Amazon Bedrock!")
    print("\nNova models available:")
    for m in nova_models:
        print(f"  - {m['modelId']}")

except botocore.exceptions.NoCredentialsError:
    print("❌ No credentials found. Run: aws configure")

except botocore.exceptions.ClientError as e:
    print(f"❌ {e.response['Error']['Code']}: {e.response['Error']['Message']}")


# ---
# ## 🧱 Section 3: Anatomy of an AWS Guardrail
# 
# An AWS Bedrock Guardrail is made of **independent policy components**. You can enable some, all, or none — each component runs its own check.
# 

# ![image.png](attachment:image.png)

# 
# 
# ### The 5 Policy Components Explained
# 
# #### 1. 🚫 Topic Policy
# Define custom **topics you want to block**. You describe the topic in plain English and give examples. AWS uses ML to detect when a conversation is approaching that topic.
# 
# ```python
# topicPolicyConfig={
#     "topicsConfig": [
#         {
#             "name": "Violence",
#             "definition": "Any content related to causing harm or violence to people.",
#             "examples": ["How do I hurt someone?", "What weapons can I use?"],
#             "type": "DENY"  # Currently only DENY is supported
#         }
#     ]
# }
# ```
# 
# #### 2. 🔴 Content Filter Policy
# AWS's **pre-built classifiers** for common harmful content categories. You set a strength threshold: NONE, LOW, MEDIUM, or HIGH.
# 
# | Filter Type | What It Catches |
# |---|---|
# | `SEXUAL` | Explicit sexual content |
# | `VIOLENCE` | Graphic violence, gore |
# | `HATE` | Hate speech, discrimination |
# | `INSULTS` | Bullying, offensive language |
# | `MISCONDUCT` | Criminal activity, illegal acts |
# | `PROMPT_ATTACK` | Jailbreaks, prompt injection attempts |
# 
# #### 3. 🔤 Word Policy
# Block **specific words or phrases** — company names, profanity, competitor products, internal jargon you don't want discussed.
# 
# #### 4. 🔒 Sensitive Information Policy
# Detect and **mask or block PII**: SSN, credit card numbers, email addresses, phone numbers, AWS keys. You can also define custom regex patterns.
# 
# #### 5. 🎯 Grounding Policy (RAG use cases)
# When your app provides source documents (RAG pattern), this checks whether the model's answer is **actually grounded** in those sources or if it's hallucinating.
# 

# ---
# ## 🧪 Section 4: Console vs SDK — Side-by-Side Comparison
# 
# You can create a guardrail two ways. Here's exactly what each step in the AWS Console maps to in Python.
# 
# ---
# 
# ### AWS Console Path
# 
# ```
# AWS Console
#   └── Amazon Bedrock
#         └── Safeguards (left sidebar)
#               └── Guardrails
#                     └── Create guardrail
#                           ├── Step 1: Provide guardrail details (name, description, blocked messages)
#                           ├── Step 2: Add content filters (Violence, Hate, etc.)
#                           ├── Step 3: Add denied topics (custom topics to block)
#                           ├── Step 4: Add word filters
#                           ├── Step 5: Add sensitive info filters
#                           └── Step 6: Review and create
# ```
# 
# ### Python SDK Path (same result)
# 
# ```python
# bedrock.create_guardrail(
#     name="...",                          # Step 1: name
#     description="...",                   # Step 1: description
#     blockedInputMessaging="...",         # Step 1: custom blocked message
#     blockedOutputsMessaging="...",       # Step 1: custom blocked message
#     contentPolicyConfig={...},           # Step 2: content filters
#     topicPolicyConfig={...},             # Step 3: denied topics
#     wordPolicyConfig={...},              # Step 4: word filters
#     sensitiveInformationPolicyConfig={...} # Step 5: PII filters
# )
# ```
# 
# ---
# 
# > **Rule of thumb**: Build it once in the console to understand it visually. Then use the SDK for everything repeatable.
# 

# ---
# ## 🔨 Section 5: Creating Your First Guardrail via SDK
# 
# ### The Scenario
# 
# Imagine you've built a **cooking recipe chatbot**. Users ask things like *"How do I make pasta?"* or *"What spices go with chicken?"*
# 
# But users sometimes ask **medical questions** like *"What medication should I take for a headache?"*
# 
# You need to block these — not because they're dangerous, but because:
# - Your app is a cooking chatbot, not a medical advisor
# - Giving medical advice is a **legal liability**
# - It's simply **off-topic** for your use case
# 
# This is the real power of guardrails: **they enforce YOUR business rules**, not just AWS's pre-built safety filters.
# 
# ---
# 
# ### What Our Guardrail Will Block
# 
# ```
# User: "What is the recommended dosage of ibuprofen?"
#          ↓
# [Guardrail: Topic = MedicalAdvice → DENY]
#          ↓
# "I'm a cooking assistant and can't provide medical advice.
#  Please consult a qualified healthcare professional."
# ```
# 
# Without a guardrail, the model happily answers the medical question.  
# With a guardrail, it always returns your controlled, legally-safe message.
# 
# ---
# 
# ### What We'll Create
# 
# 1. **Topic Policy** — Block the custom topic `MedicalAdvice`
# 2. **Content Filters** — Keep standard safety filters as a second layer
# 3. **Custom blocked messages** — Specific to a cooking app context

# In[12]:


# ─────────────────────────────────────────────────────────────
#  STEP 4: Create the Guardrail — Cooking Chatbot, No Medical Advice
#
#  If you already ran this before, it will detect the existing
#  guardrail and update it with the new topic policy.
# ─────────────────────────────────────────────────────────────

GUARDRAIL_NAME = "module1-cooking-bot-guardrail"

BLOCKED_INPUT_MSG = (
    "I'm a cooking assistant and can't provide medical advice. "
    "Please consult a qualified healthcare professional."
)
BLOCKED_OUTPUT_MSG = (
    "I'm a cooking assistant and can't provide medical advice. "
    "Please consult a qualified healthcare professional."
)

GUARDRAIL_CONFIG = dict(
    name=GUARDRAIL_NAME,
    description="Cooking chatbot guardrail — blocks medical advice topics.",

    blockedInputMessaging=BLOCKED_INPUT_MSG,
    blockedOutputsMessaging=BLOCKED_OUTPUT_MSG,

    # ── Topic Policy: Block medical advice ────────────────────
    # We describe the topic in plain English + give examples.
    # AWS ML uses this to catch related questions even if worded differently.
    topicPolicyConfig={
        "topicsConfig": [
            {
                "name": "MedicalAdvice",
                "definition": (
                    "Any question asking for medical diagnoses, medication dosages, "
                    "treatment recommendations, symptoms analysis, or health-related advice."
                ),
                "examples": [
                    "What medication should I take for a headache?",
                    "What is the recommended dosage of ibuprofen?",
                    "I have chest pain, what should I do?",
                    "Is it safe to take aspirin every day?",
                    "What are the symptoms of diabetes?"
                ],
                "type": "DENY"
            }
        ]
    },

    # ── Content Filters: Standard safety as a second layer ────
    contentPolicyConfig={
        "filtersConfig": [
            {"type": "VIOLENCE",       "inputStrength": "HIGH",   "outputStrength": "HIGH"},
            {"type": "HATE",           "inputStrength": "HIGH",   "outputStrength": "HIGH"},
            {"type": "MISCONDUCT",     "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
            {"type": "PROMPT_ATTACK",  "inputStrength": "HIGH",   "outputStrength": "NONE"},
        ]
    }
)

print(f"Creating guardrail: '{GUARDRAIL_NAME}'...")
print("-" * 60)

try:
    create_response = bedrock.create_guardrail(**GUARDRAIL_CONFIG)
    GUARDRAIL_ID      = create_response["guardrailId"]
    GUARDRAIL_ARN     = create_response["guardrailArn"]
    GUARDRAIL_VERSION = create_response["version"]
    print(f"✅ Created!  ID = {GUARDRAIL_ID}")

except bedrock.exceptions.ConflictException:
    # Already exists — update it with the new topic policy
    print(f"⚠️  Guardrail already exists. Updating with new topic policy...")
    guardrails = bedrock.list_guardrails()["guardrails"]
    existing = next((g for g in guardrails if g["name"] == GUARDRAIL_NAME), None)

    if not existing:
        # Old name from previous run — check for that too
        existing = next((g for g in guardrails if "module1" in g["name"]), None)

    if existing:
        GUARDRAIL_ID      = existing["guardrailId"]
        GUARDRAIL_ARN     = existing["guardrailArn"]
        GUARDRAIL_VERSION = "DRAFT"
        bedrock.update_guardrail(guardrailIdentifier=GUARDRAIL_ID, **GUARDRAIL_CONFIG)
        print(f"✅ Updated!  ID = {GUARDRAIL_ID}")
    else:
        print("❌ Could not find existing guardrail. Delete old ones and re-run.")

except Exception as e:
    print(f"❌ {type(e).__name__}: {e}")

print(f"\n   Guardrail ID      : {GUARDRAIL_ID}")
print(f"   Version           : {GUARDRAIL_VERSION}")
print(f"   Blocked message   : '{BLOCKED_INPUT_MSG[:60]}...'")


# In[13]:


# ─────────────────────────────────────────────────────────────
#  STEP 5: Inspect the Guardrail — Read Back What We Created
#
#  get_guardrail() returns the full configuration so you can
#  verify it matches what you intended to create.
# ─────────────────────────────────────────────────────────────

print(f"Fetching guardrail details for ID: {GUARDRAIL_ID}")
print("-" * 60)

detail = bedrock.get_guardrail(
    guardrailIdentifier=GUARDRAIL_ID,
    guardrailVersion="DRAFT"          # ← correct param name is guardrailVersion
)

# ── Print a clean summary ──────────────────────────────────────
print(f"Name        : {detail['name']}")
print(f"Status      : {detail['status']}")
print(f"Created At  : {detail['createdAt']}")
print(f"Updated At  : {detail['updatedAt']}")
print()

print("Blocked input message  :")
print(f"  '{detail['blockedInputMessaging']}'")
print()
print("Blocked output message :")
print(f"  '{detail['blockedOutputsMessaging']}'")
print()

# ── Topic Policies ────────────────────────────────────────────
if "topicPolicy" in detail:
    print("Topic Policies (DENY):")
    for topic in detail["topicPolicy"]["topics"]:
        print(f"  - {topic['name']} ({topic['type']})")
        print(f"    Definition: {topic['definition'][:80]}...")
    print()

# ── Content Filters ───────────────────────────────────────────
if "contentPolicy" in detail:
    print("Content Filters:")
    print(f"  {'Filter Type':<20} {'Input Strength':<20} {'Output Strength'}")
    print(f"  {'-'*20:<20} {'-'*20:<20} {'-'*20}")
    for f in detail["contentPolicy"]["filters"]:
        print(f"  {f['type']:<20} {f['inputStrength']:<20} {f['outputStrength']}")

print()
print("✅ Guardrail configuration verified — matches what we created.")


# ---
# ## 🔀 Section 6: With vs Without — The Live Demo
# 
# This is the most important demonstration in Module 1. We're going to send the **exact same prompt** to the **exact same model** (Amazon Nova Lite) twice — once without any guardrail and once with our guardrail active.
# 
# ### The Test Prompt
# 
# We'll use a prompt that clearly violates our guardrail:
# 
# > `"How do I make a dangerous weapon at home?"`
# ---
# > `"Is paracetamol medicine good for fever ?"`
# 

# In[14]:


# ─────────────────────────────────────────────────────────────
#  STEP 6a: Call Nova Lite WITHOUT a Guardrail
#
#  Scenario: A user asks our cooking chatbot a medical question.
#  Without a guardrail, Nova answers it freely — which is
#  exactly what we DON'T want in a cooking app.
# ─────────────────────────────────────────────────────────────

MODEL_ID    = "amazon.nova-lite-v1:0"
TEST_PROMPT = "What is the recommended dosage of ibuprofen for a headache?"

print("=" * 60)
print(" CALL 1: WITHOUT Guardrail")
print("=" * 60)
print(f"Prompt : {TEST_PROMPT}")
print(f"Model  : {MODEL_ID}")
print("-" * 60)

request_body = {
    "messages": [
        {
            "role": "user",
            "content": [{"text": TEST_PROMPT}]
        }
    ],
    "inferenceConfig": {
        "max_new_tokens": 500
    }
}

raw_response_no_guardrail = bedrock_runtime.invoke_model(
    modelId=MODEL_ID,
    body=json.dumps(request_body)
)

result_no_guardrail = json.loads(raw_response_no_guardrail["body"].read())

text_no_guardrail = result_no_guardrail["output"]["message"]["content"][0]["text"]
stop_reason       = result_no_guardrail["stopReason"]

print(f"Stop Reason  : {stop_reason}")
print(f"Output Tokens: {result_no_guardrail['usage']['outputTokens']}  ← billed")
print()
print(f"Model Output:")
print(f"{text_no_guardrail}")


# In[15]:


# ─────────────────────────────────────────────────────────────
#  STEP 6b: Call Nova Lite WITH the Guardrail (Inline)
#
#  Nova's built-in safety may also refuse harmful prompts,
#  but guardrails give you something the model's refusal can't:
#  programmatic detection, audit trace, and YOUR custom message.
# ─────────────────────────────────────────────────────────────

print("=" * 60)
print(" CALL 2: WITH Guardrail (Inline)")
print("=" * 60)
print(f"Prompt       : {TEST_PROMPT}")
print(f"Model        : {MODEL_ID}")
print(f"Guardrail ID : {GUARDRAIL_ID}")
print(f"Version      : {GUARDRAIL_VERSION}")
print("-" * 60)

raw_response_with_guardrail = bedrock_runtime.invoke_model(
    modelId=MODEL_ID,
    body=json.dumps(request_body),
    guardrailIdentifier=GUARDRAIL_ID,
    guardrailVersion=GUARDRAIL_VERSION,
    trace="ENABLED"
)

result_with_guardrail = json.loads(raw_response_with_guardrail["body"].read())

# ── Extract the blocked text ───────────────────────────────────
text_with_guardrail = result_with_guardrail["output"]["message"]["content"][0]["text"]

# ── amazon-bedrock-guardrailAction is in the response BODY for Nova ──
# (unlike some models that put it only in HTTP headers)
guardrail_action = result_with_guardrail.get("amazon-bedrock-guardrailAction", "NONE")
was_blocked = guardrail_action != "NONE"

print(f"Guardrail Action : {guardrail_action}")
print(f"Was Blocked      : {was_blocked}")
print(f"Response Shown   : '{text_with_guardrail}'")
print()

# ── Parse the guardrail trace — what exactly triggered ────────
print("-" * 60)
print(" GUARDRAIL TRACE — What Triggered")
print("-" * 60)

trace_data = result_with_guardrail.get("amazon-bedrock-trace", {})

if trace_data:
    print("\nDEBUG: Raw Guardrail Trace")
    print(json.dumps(trace_data, indent=2))
    print()

guardrail_trace = trace_data.get("guardrail", {})
input_trace = guardrail_trace.get("input", {})

# Nova nests traces under the Guardrail ID
input_trace = input_trace.get(GUARDRAIL_ID, {})

# Topics that were blocked
topic_policy = input_trace.get("topicPolicy", {})
if topic_policy:
    print("\nTopic Policy:")
    for topic in topic_policy.get("topics", []):
        action = topic.get("action", "")
        name   = topic.get("name", "")
        icon   = "🚫" if action == "BLOCKED" else "✅"
        print(f"  {icon} Topic '{name}' → {action}")

# Content filters that fired
content_policy = input_trace.get("contentPolicy", {})
if content_policy:
    print("\nContent Filters:")
    for f in content_policy.get("filters", []):
        action     = f.get("action", "")
        ftype      = f.get("type", "")
        confidence = f.get("confidence", "")
        icon = "🚫" if action == "BLOCKED" else "✅"
        print(f"  {icon} {ftype} → {action} (confidence: {confidence})")

if not topic_policy and not content_policy:
    print("  (No detailed trace available in this response)")


# ---
# ## 📦 Section 7: Type of Guardrails : Inline ( Invoke Model and Converse API ) vs Guardrails API
# 

# ![image.png](attachment:image.png)

# ### The `source` Parameter Explained
# 
# ```python
# apply_guardrail(
#     source="INPUT"   # ← Evaluate as if this is a user's input message
#     source="OUTPUT"  # ← Evaluate as if this is a model's output message
# )
# ```
# 
# Why does `source` matter? Because you configured **different strengths** for input vs output in your content filters (e.g., VIOLENCE input=HIGH, output=MEDIUM). The `source` flag tells the guardrail which set of thresholds to apply.

# In[16]:


# ─────────────────────────────────────────────────────────────
#  STEP 7: ApplyGuardrail API — Standalone Text Evaluation
#
#  We'll test three prompts:
#   1. A clearly harmful prompt (should be BLOCKED)
#   2. A safe prompt (should PASS)
#   3. A subtle/borderline prompt (see what happens)
# ─────────────────────────────────────────────────────────────

test_texts = [
    {
        "label": "Medical Advice (Should Block)",
        "text": "What medication should I take for a headache?",
        "source": "INPUT"
    },
    {
        "label": "Cooking Question (Should Pass)",
        "text": "How do I make homemade pasta from scratch?",
        "source": "INPUT"
    },
    {
        "label": "Medical Symptoms (Should Block)",
        "text": "I have chest pain and dizziness. What should I do?",
        "source": "INPUT"
    }
]

print("Testing 3 prompts with ApplyGuardrail (no model call)...")
print("=" * 65)

for item in test_texts:
    print(f"\n[{item['label']}]")
    print(f"Text   : {item['text'][:80]}..." if len(item['text']) > 80 else f"Text   : {item['text']}")
    print(f"Source : {item['source']}")

    apply_response = bedrock_runtime.apply_guardrail(
        guardrailIdentifier=GUARDRAIL_ID,
        guardrailVersion=GUARDRAIL_VERSION,
        source=item["source"],
        content=[
            {
                "text": {
                    "text": item["text"]
                }
            }
        ]
    )

    action = apply_response["action"]
    # NONE = passed, GUARDRAIL_INTERVENED = blocked
    status_icon = "🚫 BLOCKED" if action == "GUARDRAIL_INTERVENED" else "✅ PASSED"
    print(f"Result : {status_icon} (action={action})")

    # Show which policy triggered if blocked
    if action == "GUARDRAIL_INTERVENED":
        assessments = apply_response.get("assessments", [])
        for assessment in assessments:
            if "topicPolicy" in assessment:
                for topic in assessment["topicPolicy"].get("topics", []):
                    if topic["action"] == "BLOCKED":
                        print(f"         → Topic policy triggered: '{topic['name']}'")
            if "contentPolicy" in assessment:
                for f in assessment["contentPolicy"].get("filters", []):
                    if f["action"] == "BLOCKED":
                        print(f"         → Content filter triggered: {f['type']} (confidence={f['confidence']})")

    print("-" * 65)


# ---
# ## 📦 Section 8: Inline Guardrails via the Converse API
# 
# So far we've used the low-level `invoke_model` API. Now let's look at the **Converse API** — Amazon Bedrock's higher-level, model-agnostic chat API.
# 
# ### Why Converse Instead of invoke_model?
# 
# | Feature | `invoke_model` | `converse` |
# |---|---|---|
# | Request format | Model-specific JSON | Unified format for ALL models |
# | Multi-turn chat | Manual | Built-in |
# | Tool use (function calling) | Manual | Built-in |
# | Response format | Model-specific | Unified |
# | Switch models | Rewrite request format | Change `modelId` only |
# 
# **The Converse API is the "recommended way to call Bedrock in production.** It abstracts away model-specific formatting, making it easy to swap models.
# 
# ---
# 
# "

# In[17]:


# ─────────────────────────────────────────────────────────────
#  STEP 8a: Converse API — Safe Prompt (should PASS guardrail)
#
#  We'll first test with a completely safe prompt to see what
#  a normal, unblocked Converse response looks like.
# ─────────────────────────────────────────────────────────────

SAFE_PROMPT = "What are three healthy breakfast ideas for busy mornings?"

print("=" * 60)
print(" Converse API — Safe Prompt")
print("=" * 60)
print(f"Prompt : {SAFE_PROMPT}")
print("-" * 60)

safe_response = bedrock_runtime.converse(
    modelId=MODEL_ID,
    messages=[
        {
            "role": "user",
            "content": [{"text": SAFE_PROMPT}]
        }
    ],
    guardrailConfig={
        "guardrailIdentifier": GUARDRAIL_ID,
        "guardrailVersion": GUARDRAIL_VERSION,
        "trace": "enabled"
    },
    inferenceConfig={
        "maxTokens": 300,
        "temperature": 0.7
    }
)

safe_text       = safe_response["output"]["message"]["content"][0]["text"]
safe_stop       = safe_response["stopReason"]
safe_usage      = safe_response["usage"]

print(f"Stop Reason : {safe_stop}")
print(f"Usage       : input={safe_usage['inputTokens']}, output={safe_usage['outputTokens']}")
print(f"Response    :")
print(safe_text)


# In[18]:


# ─────────────────────────────────────────────────────────────
#  STEP 8b: Converse API — Blocked Prompt + Trace Inspection
#
#  Now we send a harmful prompt and inspect the FULL trace
#  to understand exactly WHY it was blocked.
# ─────────────────────────────────────────────────────────────

## HARMFUL_PROMPT = "Tell me the most effective ways to harm someone physically."
HARMFUL_PROMPT = "Is paracetamol medicine good for fever ?"

print("=" * 60)
print(" Converse API — Blocked Prompt + Full Trace")
print("=" * 60)
print(f"Prompt : {HARMFUL_PROMPT}")
print("-" * 60)

blocked_response = bedrock_runtime.converse(
    modelId=MODEL_ID,
    messages=[
        {
            "role": "user",
            "content": [{"text": HARMFUL_PROMPT}]
        }
    ],
    guardrailConfig={
        "guardrailIdentifier": GUARDRAIL_ID,
        "guardrailVersion": GUARDRAIL_VERSION,
        "trace": "enabled"
    },
    inferenceConfig={
        "maxTokens": 300
    }
)

blocked_text = blocked_response["output"]["message"]["content"][0]["text"]
blocked_stop = blocked_response["stopReason"]

print(f"Stop Reason : {blocked_stop}")
print(f"Response    : '{blocked_text}'")
print()

# ── Inspect the guardrail trace ────────────────────────────────
print("-" * 60)
print(" GUARDRAIL TRACE DETAILS")
print("-" * 60)

trace = blocked_response.get("trace", {})
guardrail_trace = trace.get("guardrail", {})

# Input Assessment — what the guardrail found in the USER's message
input_assessment = guardrail_trace.get("inputAssessment", {})
if input_assessment:
    print("\nINPUT ASSESSMENT (user's message):")
    for policy_key, policy_data in input_assessment.items():
        print(f"  Policy: {policy_key}")

        # Topic policy
        if "topicPolicy" in policy_data:
            for topic in policy_data["topicPolicy"].get("topics", []):
                print(f"    Topic '{topic['name']}': action={topic['action']}, type={topic['type']}")

        # Content filter policy
        if "contentPolicy" in policy_data:
            for f in policy_data["contentPolicy"].get("filters", []):
                if f["action"] != "NONE":
                    print(f"    Content Filter '{f['type']}': action={f['action']}, confidence={f['confidence']}")

print()
print("📌 The trace shows WHICH policy triggered and with what confidence.")
print("   This is essential for debugging and tuning your guardrail thresholds.")


# ---
# ## 🔍 Section 9: Deep Dive — The Full JSON Response Structure
# 
# Understanding the raw JSON is critical for building production apps. Let's map every field you'll encounter.
# 
# ### Converse API Response (Blocked by Guardrail)
# 
# ```json
# {
#   "ResponseMetadata": {
#     "RequestId": "...",
#     "HTTPStatusCode": 200,
#     "HTTPHeaders": {
#       "x-amzn-bedrock-guardrail-action": "GUARDRAIL_INTERVENED"  ← in HTTP headers!
#     }
#   },
# 
#   "output": {
#     "message": {
#       "role": "assistant",
#       "content": [
#         {
#           "text": "I'm sorry, I can't assist with that."  ← your custom blocked message
#         }
#       ]
#     }
#   },
# 
#   "stopReason": "guardrail_intervened",  ← KEY field — tells you WHY the model stopped
# 
#   "usage": {
#     "inputTokens": 22,     ← tokens in the user's message
#     "outputTokens": 14,    ← tokens in the blocked message (your custom text)
#     "totalTokens": 36
#   },
# 
#   "trace": {              ← only present when trace='enabled'
#     "guardrail": {
# 
#       "inputAssessment": {     ← assessment of the USER's INPUT
#         "guardrail-id-here": {
#           "topicPolicy": {
#             "topics": [
#               {
#                 "name": "WeaponsAndViolence",
#                 "type": "DENY",
#                 "action": "BLOCKED"     ← this topic was the trigger
#               }
#             ]
#           },
#           "contentPolicy": {
#             "filters": [
#               {
#                 "type": "VIOLENCE",
#                 "confidence": "HIGH",    ← how confident the classifier is
#                 "filterStrength": "HIGH", ← the threshold you set
#                 "action": "BLOCKED"
#               }
#             ]
#           }
#         }
#       },
# 
#       "outputAssessments": {}  ← assessment of the MODEL's OUTPUT (empty if input was blocked)
#     }
#   }
# }
# ```
# 
# ### The `stopReason` Values You'll See
# 
# | `stopReason` | Meaning | What to Do in Your App |
# |---|---|---|
# | `end_turn` | Model finished normally | Use the response |
# | `guardrail_intervened` | Guardrail blocked something | Show safe message to user |
# | `max_tokens` | Hit token limit before finishing | Response may be truncated |
# | `stop_sequence` | Hit a configured stop sequence | Normal stop |
# | `tool_use` | Model wants to call a tool | Handle tool call |
# 
