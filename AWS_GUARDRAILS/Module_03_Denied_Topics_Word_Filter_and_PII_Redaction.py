#!/usr/bin/env python
# coding: utf-8

# # 🗂️ Module 3: Denied Topics, Word Filters & PII Redaction
# ## AWS Bedrock Guardrails — Controlling Topics, Words, and Sensitive Data
# 
# ---
# 
# > **Course**: AWS Guardrails — Scratch to Advanced  
# > **Module**: 3   
# > **What We Build**: A production-ready coding assistant guardrail that refuses legal/medical advice and masks all PII
# 
# ---
# 
# ### The Problem We're Solving
# 
# You've built a **coding assistant** — users ask Python, AWS, and database questions. But three things keep happening:
# 
# 1. Users ask **legal and medical questions** — your app isn't qualified for those
# 2. Users paste **their real SSN, credit card, or password** into code snippets — your logs now contain sensitive data
# 3. Users mention **competitor tools** you've decided to stay neutral about
# 
# This module shows you exactly how to fix all three.
# 
# ---
# 
# ### Three Tools, Three Problems
# 
# | Tool | Solves | How It Works |
# |---|---|---|
# | **Denied Topics** | Off-topic questions | AI semantic matching — understands meaning, not just keywords |
# | **Word Policy** | Specific words/phrases | Exact string match — fast, deterministic |
# | **PII Policy** | Sensitive data leakage | Entity detection + ANONYMIZE or BLOCK |
# 
# ---
# 
# 

# In[1]:


# ─────────────────────────────────────────────────────────────
#  Setup — same as previous modules
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
#  Reusable Helpers (same pattern as Module 2)
# ─────────────────────────────────────────────────────────────

def create_or_get_guardrail(name, **kwargs):
    """Create a guardrail or fetch existing one by name."""
    try:
        resp = bedrock.create_guardrail(name=name, **kwargs)
        print(f"✅ Created  : {name}  (ID: {resp['guardrailId']})")
        return resp["guardrailId"], resp["version"]
    except bedrock.exceptions.ConflictException:
        guardrails = bedrock.list_guardrails()["guardrails"]
        existing = next((g for g in guardrails if g["name"] == name), None)
        if existing:
            gid = existing["guardrailId"]
            # Update to make sure config is current
            bedrock.update_guardrail(guardrailIdentifier=gid, name=name, **kwargs)
            print(f"🔄 Updated  : {name}  (ID: {gid})")
            return gid, "DRAFT"
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        return None, None


def apply_check(text, guardrail_id, source="INPUT", version="DRAFT"):
    resp = bedrock_runtime.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=version,
        source=source,
        content=[{"text": {"text": text}}]
    )

    action = resp["action"]
    outputs = resp.get("outputs", [])
    output_text = outputs[0].get("text", "") if outputs else ""

    intervened = action == "GUARDRAIL_INTERVENED"

    return {
        "intervened": intervened,
        "action": action,
        "output": output_text,
        "raw": resp
    }


def print_result(label, text, result):
    icon = "⚠️ INTERVENED" if result["intervened"] else "✅ PASSED"

    print(f"{icon} [{label}]")
    print(f"Input  : {text}")

    if result["output"]:
        print(f"Output : {result['output']}")

    print(f"Action : {result['action']}")
    print()

print("✅ Helpers ready: create_or_get_guardrail(), apply_check(), print_result()")


# ---
# ## 🗂️ Section 1: Denied Topics
# 
# ---

# ![image.png](attachment:image.png)

# ### How to Write a Good Topic Definition
# 
# The definition quality directly affects accuracy. Here's the difference:
# 
# **Weak definition:**
# ```python
# "definition": "Legal stuff"
# ```
# Too vague — AWS doesn't know what "legal stuff" means in your context.
# 
# **Strong definition:**
# ```python
# "definition": (
#     "Requests for legal advice, legal opinions, interpretation of laws or contracts, "
#     "guidance on legal rights, recommendations about lawsuits, or any question that "
#     "requires the expertise of a licensed attorney."
# )
# ```
# Specific, scoped, and clear — AWS knows exactly what to catch.
# 
# ---
# 
# ### Tips for Writing Good Examples
# 
# - Provide **4–5 diverse examples** — different phrasings of the same intent
# - Cover **edge cases** — indirect or politely-phrased versions of the request
# - Don't just list obvious versions — include how a real user might actually phrase it
# 
# ```python
# "examples": [
#     "Can I sue my employer for wrongful termination?",      # direct
#     "Is this contract legally binding?",                    # specific
#     "What are my rights if my landlord does this?",         # indirect
#     "Do I need a lawyer for this situation?",               # meta
#     "How long do I have to file a lawsuit?",                # procedural
# ]
# ```
# 

# In[3]:


# ─────────────────────────────────────────────────────────────
#  Create a Denied Topics Guardrail
#  Scenario: Coding assistant — refuses legal and medical advice
# ─────────────────────────────────────────────────────────────

TOPIC_GUARDRAIL_ID, _ = create_or_get_guardrail(
    name="mod3-denied-topics",
    description="Coding assistant — blocks legal and medical advice topics.",
    blockedInputMessaging=(
        "I'm a coding assistant and can only help with programming questions. "
        "For legal or medical questions, please consult a qualified professional."
    ),
    blockedOutputsMessaging=(
        "I'm a coding assistant and can only help with programming questions. "
        "For legal or medical questions, please consult a qualified professional."
    ),
    topicPolicyConfig={
        "topicsConfig": [
            {
                "name": "LegalAdvice",
                "definition": (
                    "Requests for legal advice, legal opinions, interpretation of laws, "
                    "guidance on legal rights, or recommendations about lawsuits "
                    "requiring a licensed attorney."
                ),
                "examples": [
                    "Can I sue my employer for wrongful termination?",
                    "Is this contract legally binding?",
                    "What are my rights if my landlord does this?",
                    "Do I need a lawyer for this situation?",
                    "How long do I have to file a lawsuit?",
                ],
                "type": "DENY"
            },
            {
                "name": "MedicalAdvice",
                "definition": (
                    "Requests for medical diagnoses, treatment recommendations, medication "
                    "dosages, interpretation of medical symptoms, or any health-related "
                    "guidance that requires a licensed medical professional."
                ),
                "examples": [
                    "What medication should I take for this symptom?",
                    "I have chest pain, what should I do?",
                    "Is this dosage of ibuprofen safe?",
                    "Can you diagnose what's wrong with me?",
                    "What are the side effects of this drug?",
                ],
                "type": "DENY"
            }
        ]
    }
)

print(f"\nTopic Guardrail ID: {TOPIC_GUARDRAIL_ID}")


# In[4]:


# ─────────────────────────────────────────────────────────────
#  Test Denied Topics — Precision Testing
#
#  Key question: does the guardrail catch different phrasings?
#  A good topic definition catches the INTENT, not just keywords.
# ─────────────────────────────────────────────────────────────

topic_tests = [
    # ── Legal ─────────────────────────────────────────────────
    ("Legal - Direct",    "Can I sue my employer for firing me unfairly?"),
    ("Legal - Indirect",  "What are my rights if my landlord won't fix the heating?"),
    ("Legal - Subtle",    "My neighbour damaged my car. What steps can I take?"),
    ("Legal - No keyword","I think I was treated unfairly at work. What options do I have?"),

    # ── Medical ───────────────────────────────────────────────
    ("Medical - Direct",  "What is the recommended dose of paracetamol for a child?"),
    ("Medical - Indirect", "I have a rash that won't go away. What could it be?"),
    ("Medical - Subtle",  "Is it safe to mix ibuprofen and alcohol?"),

    # ── On-topic for coding assistant (should all PASS) ───────
    ("Code - Pass",       "How do I reverse a string in Python?"),
    ("Code - Pass",       "What is the difference between a list and a tuple?"),
    ("Code - Pass",       "Can you help me write a SQL query for joining two tables?"),
    # Edge: mentions legal but is a coding question
    ("Code - Edge",       "How do I build a legal document parser in Python?"),
    # Edge: mentions medical but is a coding question
    ("Code - Edge",       "How do I connect my app to a medical records database API?"),
]

print("=" * 70)
print(" DENIED TOPICS — Precision Test")
print("=" * 70)
print()

for label, text in topic_tests:
    result = apply_check(text, TOPIC_GUARDRAIL_ID)
    print_result(label, text, result)


# ---
# ## 📝 Section 2: Word & Phrase Blocklists
# 
# ### What Is the Word Policy?
# 
# The word policy does **exact string matching** — if a specified word or phrase appears anywhere in the input or output, it's blocked. No AI, no semantics — pure text search.
# 
# ```
# Word blocklist: ["CompetitorX", "secret_project"]
# 
# "Tell me about CompetitorX"       → BLOCKED (exact match)
# "CompetitorX is worse than us"    → BLOCKED
# "What about the competitor?"      → PASSED (different word)
# "Tell me about competitorx"       → BLOCKED (case-insensitive)
# ```
# 
# ---
# 
# ### Two Components
# 
# #### 1. Custom Word List
# Words and phrases **you define**. Use cases:
# - Competitor product names
# - Internal project codenames that shouldn't appear in responses
# - Trademark terms you want to avoid
# - Sensitive internal terminology
# 
# ```python
# "wordsConfig": [
#     {"text": "CompetitorX"},
#     {"text": "secret_project_alpha"},
#     {"text": "internal codename"},
# ]
# ```
# 
# #### 2. Managed Profanity List
# AWS maintains a **built-in profanity list** — thousands of offensive words across multiple languages. You don't maintain it; AWS does.
# 
# ```python
# "managedWordListsConfig": [
#     {"type": "PROFANITY"}  # only option currently
# ]
# ```
# 
# ---

# In[5]:


# ─────────────────────────────────────────────────────────────
#  Create Word Policy Guardrail
#
#  Scenario: Our coding assistant should not discuss
#  competitor tools, internal project codenames, or profanity.
# ─────────────────────────────────────────────────────────────

WORD_GUARDRAIL_ID, _ = create_or_get_guardrail(
    name="mod3-word-policy",
    description="Word policy demo — custom words + managed profanity.",
    blockedInputMessaging="Your message contains a word or phrase that isn't allowed in this assistant.",
    blockedOutputsMessaging="The response contained a restricted word or phrase and was blocked.",

    wordPolicyConfig={
        # ── Custom words you define ────────────────────────────
        "wordsConfig": [
            {"text": "CompetitorX"},           # fictional competitor name
            {"text": "CompetitorY"},           # another competitor
            {"text": "ProjectNightingale"},    # internal codename
            {"text": "internal_api_key_v2"},   # specific secret string
        ],
        # ── AWS managed profanity list ─────────────────────────
        "managedWordListsConfig": [
            {"type": "PROFANITY"}
        ]
    }
)

print(f"\nWord Policy Guardrail ID: {WORD_GUARDRAIL_ID}")


# In[8]:


# ─────────────────────────────────────────────────────────────
#  Test Word Policy
# ─────────────────────────────────────────────────────────────

word_tests = [
    # Custom words — should block
    ("Competitor name",     "How does CompetitorX handle authentication?"),
    ("Another competitor",  "Is CompetitorY better than your product?"),
    ("Internal codename",   "Tell me about ProjectNightingale."),
    ("Secret string",       "The endpoint uses internal_api_key_v2 as the header."),

    # Profanity — managed list
    ("Profanity",           "This damn code keeps breaking! You piece of shit and go die."),  # mild — may or may not block

    # Paraphrasing — should PASS (word policy doesn't do semantics)
    ("Paraphrase pass",     "How does that other authentication tool work?"),
    ("Paraphrase pass",     "Tell me about the project with the bird name."),

    # Safe
    ("Safe - code",         "How do I handle authentication in FastAPI?"),
    ("Safe - code",         "What is a JWT token?"),
]

print("=" * 70)
print(" WORD POLICY TEST")
print("=" * 70)
print()

for label, text in word_tests:
    result = apply_check(text, WORD_GUARDRAIL_ID)
    print_result(label, text, result)

print("─" * 70)


# ---
# ## 🔍 Section 3: Custom Regex Patterns
# 
# ### What Are Regex Patterns in Guardrails?
# 
# Regex (Regular Expression) patterns let you define **custom structured data patterns** to detect and block. While AWS's built-in PII detection handles common types (SSN, email, etc.), regex lets you catch **your own specific formats** — things AWS doesn't know about.
# 
# ---
# 
# ### When to Use Custom Regex vs Built-in PII Detection
# 
# | Use | Approach |
# |---|---|
# | Detect SSN (US format) | Built-in PII entity `US_SOCIAL_SECURITY_NUMBER` |
# | Detect email addresses | Built-in PII entity `EMAIL` |
# | Detect **your company's** employee ID format `EMP-XXXXX` | Custom regex |
# | Detect internal ticket numbers `TKT-2025-XXXXX` | Custom regex |
# | Detect a specific API key format | Custom regex |
# 
# ---
# 
# ### How Regex Config Works
# 
# ```python
# "regexesConfig": [
#     {
#         "name": "EmployeeID",          # your label for this pattern
#         "description": "Company employee ID format EMP-XXXXX",
#         "pattern": "EMP-\\d{5}",       # the regex (note: double backslash in Python strings)
#         "action": "ANONYMIZE"          # ANONYMIZE or BLOCK
#     }
# ]
# ```
# 
# ### Common Regex Patterns Reference
# 
# ```python
# # US Phone number (various formats)
# r"(\+1)?[-.\s]?(\(?\d{3}\)?)[-. ]?(\d{3})[-. ]?(\d{4})"
# 
# # US Social Security Number
# r"\d{3}-\d{2}-\d{4}"
# 
# # Credit card (basic 16-digit)
# r"\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}"
# 
# # AWS Access Key format
# r"AKIA[0-9A-Z]{16}"
# 
# # Company employee ID (example)
# r"EMP-\d{5}"
# 
# # Internal ticket number (example)
# r"TKT-\d{4}-\d{5}"
# ```
# 
# > ⚠️ **Double backslash in Python strings**: In a Python string, `\d` must be written as `\\d` because a single backslash is an escape character. Or use a raw string `r"\d{3}"` — but in the API call (which is a regular string), use `\\d`.
# 

# In[9]:


# ─────────────────────────────────────────────────────────────
#  Create Guardrail with Custom Regex Patterns
# ─────────────────────────────────────────────────────────────

REGEX_GUARDRAIL_ID, _ = create_or_get_guardrail(
    name="mod3-regex-patterns",
    description="Custom regex pattern demo.",
    blockedInputMessaging="Your message contains sensitive data patterns that are not allowed.",
    blockedOutputsMessaging="The response contained sensitive data patterns and was blocked.",

    sensitiveInformationPolicyConfig={
        "regexesConfig": [
            {
                "name": "EmployeeID",
                "description": "Internal employee ID format: EMP-XXXXX",
                "pattern": "EMP-\\d{5}",
                "action": "ANONYMIZE"
            },
            {
                "name": "InternalTicket",
                "description": "Internal support ticket: TKT-YYYY-XXXXX",
                "pattern": "TKT-\\d{4}-\\d{5}",
                "action": "ANONYMIZE"
            },
            {
                "name": "AWSAccessKey",
                "description": "AWS Access Key format",
                "pattern": "AKIA[0-9A-Z]{16}",
                "action": "BLOCK"
            },
        ]
    }
)

print(f"\nRegex Guardrail ID: {REGEX_GUARDRAIL_ID}")


# In[10]:


# ─────────────────────────────────────────────────────────────
# Test Custom Regex Patterns
# Shows ANONYMIZE vs BLOCK behavior
# ─────────────────────────────────────────────────────────────

regex_tests = [
    (
        "Employee ID",
        "Please look into the issue for employee EMP-84321."
    ),
    (
        "Ticket ID",
        "This is related to ticket TKT-2025-00145."
    ),
    (
        "AWS Key (BLOCK)",
        "My AWS key is AKIAIOSFODNN7EXAMPLE123."
    ),
    (
        "Safe",
        "How do I connect to an S3 bucket using boto3?"
    ),
]

print("=" * 70)
print("REGEX OUTPUT TEST")
print("=" * 70)
print()

for label, text in regex_tests:

    result = apply_check(
        text,
        REGEX_GUARDRAIL_ID,
        source="OUTPUT"
    )

    print(f"Test        : {label}")
    print(f"Input       : {text}")
    print(f"Action      : {result['action']}")
    print(f"Intervened  : {result['intervened']}")

    if result["output"]:
        print(f"Output      : {result['output']}")

    print("-" * 70)

print()


# ---
# ## 🔒 Section 4: PII Detection & Redaction
# 
# ### What Is PII?
# 
# **Personally Identifiable Information (PII)** is any data that can be used to identify a specific person. Leaking PII through your AI app can result in:
# 
# - GDPR violations (EU) — up to 4% of annual turnover in fines
# - HIPAA violations (US healthcare) — $100 to $50,000 per violation
# - PCI-DSS violations (payment cards) — fines + loss of payment processing ability
# - Reputation damage and user trust loss
# 
# ---
# 
# ### AWS Bedrock's 14 Built-in PII Entity Types
# 
# | Entity Type | What It Detects | Example |
# |---|---|---|
# | `NAME` | Full person names | John Smith |
# | `EMAIL` | Email addresses | john@example.com |
# | `PHONE` | Phone numbers | +1-555-123-4567 |
# | `US_SOCIAL_SECURITY_NUMBER` | US SSN | 123-45-6789 |
# | `CREDIT_DEBIT_CARD_NUMBER` | Card numbers | 4532-1234-5678-9012 |
# | `IP_ADDRESS` | IPv4 and IPv6 | 192.168.1.1 |
# | `ADDRESS` | Physical addresses | 123 Main St, New York |
# | `AGE` | Age mentions | 35 years old |
# | `DRIVER_ID` | Driver's license numbers | D123-456-789 |
# | `PASSPORT_NUMBER` | Passport numbers | A12345678 |
# | `AWS_ACCESS_KEY` | AWS access keys | AKIAIOSFODNN7EXAMPLE |
# | `AWS_SECRET_KEY` | AWS secret keys | wJalrXUtnFEMI/K7MDENG... |
# | `USERNAME` | Usernames | @john_doe |
# | `PASSWORD` | Passwords | supersecret123 |
# 
# ---
# 
# ### ANONYMIZE vs BLOCK — The Critical Difference
# 
# This is the most important decision in PII policy.
# 
# #### ANONYMIZE
# Replaces the PII entity with a type label. The message still goes through — but with the sensitive data masked.
# 
# ```
# Input : "My email is john@example.com and my SSN is 123-45-6789"
# After : "My email is {EMAIL} and my SSN is {US_SOCIAL_SECURITY_NUMBER}"
#          ↑ model receives this masked version, not the real values
# ```
# 
# **Use ANONYMIZE when:**
# - The message still makes sense without the actual PII value
# - You want the conversation to continue (e.g., user can still get support)
# - Logging the conversation without storing actual PII
# 
# #### BLOCK
# Stops the entire message if any PII of that type is detected.
# 
# ```
# Input : "My password is supersecret123"
# Result: GUARDRAIL_INTERVENED — blocked message, user sees error
# ```
# 
# **Use BLOCK when:**
# - The PII should never appear in your system at all
# - Compliance requires complete rejection (e.g., payment card data on non-PCI systems)
# - The message with PII removed would be meaningless anyway
# 
# ---
# 
# ### Decision Guide
# 
# ```
# EMAIL      → ANONYMIZE   (user may share for support purposes — mask it)
# PHONE      → ANONYMIZE   (same — useful context, but mask the actual number)
# NAME       → ANONYMIZE   (preserve context, remove identifier)
# SSN        → BLOCK       (no legitimate reason to paste SSN in a chat)
# CREDIT_CARD→ BLOCK       (PCI-DSS: never store or process in non-PCI system)
# PASSWORD   → BLOCK       (passwords should never appear anywhere in logs)
# AWS_KEY    → BLOCK       (leaked key = account compromise)
# IP_ADDRESS → ANONYMIZE   (useful for debugging context)
# ```
# 

# ### BLOCK works with apply_guardrail because it's a binary decision — detect → reject. Simple, works standalone.
# 
# ### ANONYMIZE doesn't work with apply_guardrail because it's a two-step process — detect → mask → pass modified text to model. The "pass to model" part requires an actual model call, so it only activates when you use the guardrail inline with converse or invoke_model.
# - regex ANONYMIZE does work with apply_guardrail — it's only the built-in PII entity types (NAME, EMAIL, PHONE, etc.) that don't work standalone.

# In[ ]:


# ─────────────────────────────────────────────────────────────
#  Create PII Detection Guardrail
#  Mix of ANONYMIZE and BLOCK based on sensitivity level
# ─────────────────────────────────────────────────────────────

PII_GUARDRAIL_ID, _ = create_or_get_guardrail(
    name="mod3-pii-detection",
    description="PII detection with ANONYMIZE and BLOCK actions.",
    blockedInputMessaging=(
        "Your message contains sensitive information (like a credit card or password) "
        "that cannot be processed here. Please remove it and try again."
    ),
    blockedOutputsMessaging=(
        "The response was blocked because it contained sensitive information."
    ),

    sensitiveInformationPolicyConfig={
        "piiEntitiesConfig": [
            {"type": "NAME",                       "action": "BLOCK"},
            {"type": "EMAIL",                      "action": "BLOCK"},
            {"type": "PHONE",                      "action": "BLOCK"},
            {"type": "ADDRESS",                    "action": "BLOCK"},
            {"type": "AGE",                        "action": "BLOCK"},
            {"type": "IP_ADDRESS",                 "action": "BLOCK"},
            {"type": "USERNAME",                   "action": "BLOCK"},
            {"type": "DRIVER_ID",                  "action": "BLOCK"},

            # ── BLOCK: reject message entirely ────────────────
            {"type": "US_SOCIAL_SECURITY_NUMBER",  "action": "BLOCK"},
            {"type": "CREDIT_DEBIT_CARD_NUMBER",   "action": "BLOCK"},
            {"type": "PASSWORD",                   "action": "BLOCK"},
            {"type": "AWS_ACCESS_KEY",             "action": "BLOCK"},
            {"type": "AWS_SECRET_KEY",             "action": "BLOCK"},
            {"type": "US_PASSPORT_NUMBER",            "action": "BLOCK"},
        ]
    }
)

print(f"\nPII Guardrail ID: {PII_GUARDRAIL_ID}")


# In[15]:


# ─────────────────────────────────────────────────────────────
# Test PII Detection — All Entity Types
# ─────────────────────────────────────────────────────────────

pii_tests = [
    ("NAME",       "INPUT", "My name Sudhanshu and I need help with my account."),
    ("EMAIL",      "INPUT", "Please send the report to gusainsudhanshu43@gmail.com by Friday."),
    ("PHONE",      "INPUT", "You can reach me at +1-555-867-5309 anytime."),
    ("ADDRESS",    "INPUT", "I live at 742 Evergreen Terrace, Springfield, IL 62701."),
    ("IP_ADDRESS", "INPUT", "The server at 192.168.0.105 is timing out intermittently."),
    ("USERNAME",   "INPUT", "My account username is @john_doe_dev on the platform."),


    ("SSN",         "INPUT", "My Social Security Number is 123-45-6789, please verify."),
    ("CREDIT CARD", "INPUT", "Charge my card: 4532 1234 5678 9012, expiry 12/27."),
    ("PASSWORD",    "INPUT", "My password is SuperSecret@123 — can you reset it?"),
    ("AWS KEY",     "INPUT", "I accidentally committed AKIAIOSFODNN7EXAMPLE to GitHub."),

  
    ("SAFE",        "INPUT", "How do I use pandas to read a CSV file?")
]

print("=" * 70)
print("PII DETECTION TEST")
print("=" * 70)
print()

for entity_type, source, text in pii_tests:

    result = apply_check(
        text=text,
        guardrail_id=PII_GUARDRAIL_ID,
        source=source
    )

    icon = "⚠️ INTERVENED" if result["intervened"] else "✅ PASSED"

    print(f"{icon} [{entity_type}]")
    print(f"Input  : {text}")

    if result["output"]:
        print(f"Output : {result['output']}")

    print(f"Action : {result['action']}")
    print("-" * 70)


# ---
# ## 🔄 Section 5: Live Scenario — Customer Support Bot Without vs With PII Guard
# 
# This is the most realistic demo in this module.
# 
# ### The Problem
# 
# A customer writes in:
# 
# > *"Hi, my order isn't arriving. My name is Sarah Johnson, email sarah.j@email.com, and I paid with card 4532-1234-5678-9012. My account SSN-verified ID is 987-65-4321. Please help!"*
# 
# **Without PII guard**: The model receives the full message including name, email, credit card, and SSN. All of this gets:
# - Sent to the LLM provider's servers
# - Written to your application logs
# - Potentially stored in conversation history
# 
# **With PII guard (ANONYMIZE + BLOCK)**:
# - Name → `{NAME}`
# - Email → `{EMAIL}`
# - Credit card → **BLOCKED** (PCI-DSS: never process)
# - SSN → **BLOCKED** (too sensitive)
# 
# The user is told to remove the sensitive info and the transaction never reaches the model.
# 

# In[16]:


# ─────────────────────────────────────────────────────────────
#  Customer Support Bot — With vs Without PII Guard
#  Using the Converse API so we can see the full model response.
# ─────────────────────────────────────────────────────────────

CUSTOMER_MESSAGE = (
    "Hi, my order isn't arriving. My name is Sarah Johnson, email sarah.j@email.com. "
    "I paid with card 4532 1234 5678 9012 and my account SSN on file is 987-65-4321. "
    "Order reference: TKT-2025-00145. Please help!"
)

SYSTEM_PROMPT = (
    "You are a helpful customer support assistant. "
    "Help the customer with their order issue. Be empathetic and professional."
)

SEP = "=" * 70

# ── CALL 1: WITHOUT PII Guard ──────────────────────────────────
print(SEP)
print(" CALL 1: WITHOUT PII Guard")
print(SEP)
print(f"Customer: {CUSTOMER_MESSAGE}")
print()

resp_no_pii = bedrock_runtime.converse(
    modelId=MODEL_ID,
    system=[{"text": SYSTEM_PROMPT}],
    messages=[{"role": "user", "content": [{"text": CUSTOMER_MESSAGE}]}],
    inferenceConfig={"maxTokens": 300}
)
response_text = resp_no_pii["output"]["message"]["content"][0]["text"]
print(f"Model Response:\n{response_text}")
print()

# ── CALL 2: WITH PII Guard ─────────────────────────────────────
print(SEP)
print(" CALL 2: WITH PII Guard")
print(SEP)
print(f"Customer: {CUSTOMER_MESSAGE}")
print()

resp_with_pii = bedrock_runtime.converse(
    modelId=MODEL_ID,
    system=[{"text": SYSTEM_PROMPT}],
    messages=[{"role": "user", "content": [{"text": CUSTOMER_MESSAGE}]}],
    guardrailConfig={
        "guardrailIdentifier": PII_GUARDRAIL_ID,
        "guardrailVersion": "DRAFT",
        "trace": "enabled"
    },
    inferenceConfig={"maxTokens": 300}
)

stop_reason  = resp_with_pii["stopReason"]
pii_response = resp_with_pii["output"]["message"]["content"][0]["text"]

print(f"Stop Reason : {stop_reason}")
print(f"Response    : {pii_response}")
print()



# In[ ]:




