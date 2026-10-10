#!/usr/bin/env python
# coding: utf-8

# In[1]:


print("Hello guys")


# In[2]:


import os, getpass
from pathlib import Path


# In[3]:


_root = Path.cwd()
while _root != _root.parent and not (_root / ".guardrails").exists():
    _root = _root.parent
if (_root / ".guardrails").exists():
    os.chdir(_root)
print("Working dir:", os.getcwd())


# In[5]:


if not os.environ.get("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your GROQ_API_KEY: ")


# In[6]:


BOT_MODEL = "groq/llama-3.3-70b-versatile"
SYSTEM_PROMPT = (
    "You are NimbusPay's customer-support assistant. "
    "NimbusPay is a digital payments app: cards, wallets, refunds, account help. "
    "Be concise, friendly, and accurate."
)

print("Config ready:", BOT_MODEL)


# ## PII Detection 

# In[10]:


from guardrails.hub import DetectPII
from guardrails import Guard, OnFailAction


# In[11]:


pii_guard = Guard().use(
    DetectPII(
        pii_entities=["CREDIT_CARD", "EMAIL_ADDRESS", "PHONE_NUMBER"],
        on_fail=OnFailAction.FIX,
        use_local=True,     # light: Presidio + spaCy small, no torch
    )
)


# In[13]:


raw = "We'll refund card 4111 1111 1111 1111 and email the receipt to jane@example.com."
out = pii_guard.validate(raw)
print(out)


# In[14]:


print("IN :", raw)
print("OUT:", out.validated_output)


# In[16]:


from guardrails.hub import CompetitorCheck
COMPETITORS = ["Stripe", "PayPal", "Square"]
BAD_TEXT = (
    "Thanks for reaching out! Honestly, Stripe has lower fees than us, "
    "and PayPal is easier to set up. But we're happy to help with your refund."
)
GOOD_TEXT = (
    "Thanks for reaching out! We're happy to help with your refund."
)


# ### With Good text

# In[17]:


comp_guard = Guard().use(
    CompetitorCheck(competitors=COMPETITORS, on_fail=OnFailAction.FILTER, use_local=True)
)
out = comp_guard.validate(GOOD_TEXT)
print("OUT:", repr(out.validated_output))


# ### With Bad text

# In[19]:


comp_guard = Guard().use(
    CompetitorCheck(competitors=COMPETITORS, on_fail=OnFailAction.FIX, use_local=True)
)
out = comp_guard.validate(BAD_TEXT)
print("OUT:", repr(out.validated_output))


# ## Toxic Language 

# In[20]:


from guardrails.hub import ToxicLanguage


# In[21]:


tox_guard = Guard().use(
    ToxicLanguage(
        threshold=0.5,
        validation_method="sentence",
        on_fail=OnFailAction.FIX,
        use_local=False, 
    )
)


# In[23]:


rude = "You are completely useless and your stupid fuck app stole my money."
out = tox_guard.validate(rude)
print("validation_passed:", out.validation_passed)
print("OUT:", repr(out.validated_output))


# In[25]:


out


# ## Restrict to Topic

# In[31]:


import json, litellm
from guardrails.hub import RestrictToTopic
from guardrails.errors import ValidationError


# In[27]:


def groq_topic_classifier(text, topics):
    resp = litellm.completion(
        model=BOT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": (
            'Return ONLY a JSON object {"topics_present": [...]} listing which of these '
            f'topics appear in the text.\nTopics: {topics}\nText: "{text}"'
        )}],
    )

    try:
        return json.loads(resp.choices[0].message.content).get("topics_present", [])
    except Exception:
        return []


# In[53]:


topic_guard = Guard().use(
    RestrictToTopic(
        valid_topics=["payments", "refunds", "accounts", "cards", "wallets"],
        invalid_topics=["politics", "medical advice", "investing tips"],
        disable_classifier=True,             # skip the transformer; no local/remote model needed
        disable_llm=False,
        llm_callable=groq_topic_classifier,  # Groq instead of OpenAI gpt-4o
        on_fail=OnFailAction.EXCEPTION,
    )
)



# In[54]:


off_topic = "Forget payments - who do you think will win the next presidential election?"


# In[57]:


try:
    out1 = topic_guard.validate(off_topic)
    print(out1)
    print("Passed (unexpected):", out.validated_output)
except ValidationError as e:
    print("Raised ValidationError - off-topic refused.")
    print("out1:", out1)
    print(str(e)[:300])


# # OnFailActions

# We are performing Multiple OnFailActions on CompetitorCheck validator

# from guardrails import Guard, OnFailAction
# from guardrails.hub import CompetitorCheck
# from guardrails.errors import ValidationError

# In[58]:


from guardrails import Guard, OnFailAction
from guardrails.hub import CompetitorCheck
from guardrails.errors import ValidationError


# In[59]:


from guardrails.hub import CompetitorCheck
COMPETITORS = ["Stripe", "PayPal", "Square"]
BAD_TEXT = (
    "Thanks for reaching out! Honestly, Stripe has lower fees than us, "
    "and PayPal is easier to set up. But we're happy to help with your refund."
)
GOOD_TEXT = (
    "Thanks for reaching out! We're happy to help with your refund."
)


# In[60]:


def competitor_guard(action):
    return Guard().use(
        CompetitorCheck(competitors=COMPETITORS, on_fail=action, use_local=True)
    )

print("Input we'll validate five ways:\n", BAD_TEXT)


# ## Fix OnFailAction

# In[61]:


guard = competitor_guard(OnFailAction.FIX)
out = guard.validate(GOOD_TEXT)
print("Output Raw response", out)
print("validation_passed:", out.validation_passed)
print("OUTPUT:\n", out.validated_output)


# In[62]:


guard = competitor_guard(OnFailAction.FIX)
out = guard.validate(BAD_TEXT)
print("Output Raw response", out)
print("validation_passed:", out.validation_passed)
print("OUTPUT:\n", out.validated_output)


# ## FILTER OnFailAction

# 

# In[63]:


guard = competitor_guard(OnFailAction.FILTER)
out = guard.validate(BAD_TEXT)
print("Output Raw response", out)
print("validation_passed:", out.validation_passed)
print("OUTPUT:\n", out.validated_output)


# ## REFRAIN OnFailAction

# 

# In[64]:


guard = competitor_guard(OnFailAction.REFRAIN)
out = guard.validate(BAD_TEXT)
print("Output Raw response", out)
print("validation_passed:", out.validation_passed)
print("OUTPUT:\n", out.validated_output)


# ## REFRAIN vs FILTER

# In[68]:


from typing import Optional
from pydantic import BaseModel, Field

STRUCTURED_JSON = (
    '{"answer": "Refunds settle within 24 hours.",'
    ' "comparison": "Honestly Stripe is cheaper than us.",'   # <- this field names a competitor
    ' "category": "refund"}'
)


# In[69]:


def structured_guard(action):
    cc = CompetitorCheck(competitors=COMPETITORS, on_fail=action, use_local=True)
    class SupportReply(BaseModel):
        answer: str
        comparison: Optional[str] = Field(default=None, json_schema_extra={"validators": [cc]})
        category: str
    return Guard.for_pydantic(SupportReply)


# In[70]:


for action in (OnFailAction.FILTER, OnFailAction.REFRAIN):
    guard = structured_guard(action)
    guard.parse(STRUCTURED_JSON)
    it = guard.history[-1].iterations[-1]
    print(f"=== {action} ===")
    print("  after parsing (sentinel placed in the bad field):")
    print("   ", it.parsed_output)
    print("  guarded_output (what the guard actually returns):")
    print("   ", it.guarded_output)
    print()


# ## EXCEPTION OnFailAction

# In[71]:


guard = competitor_guard(OnFailAction.EXCEPTION)
try:
    out = guard.validate(BAD_TEXT)
    print("Raw Output", out)
    print("Passed (unexpected):", out.validated_output)
except ValidationError as e:
    print("Error Raw Output", out)
    print("Raised ValidationError")
    print(str(e)[:300])


# ## ReASK OnFailAction

# In[73]:


reask_guard = Guard().use(
    CompetitorCheck(competitors=COMPETITORS, on_fail=OnFailAction.REASK, use_local=True)
)
res = reask_guard(
    model = BOT_MODEL,
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            "A customer asks why they should pick NimbusPay. In your answer, explicitly "
            "compare us to Stripe and PayPal by name."
        )},
    ],
    temperature = 0.3,
    num_reasks=2,
)


# In[74]:


print("FINAL OUTPUT:\n", res.validated_output)


# In[75]:


print(res)


# In[76]:


iters = reask_guard.history[-1].iterations
print("\nLLM round-trips:", len(iters), "| Reask occurred:", len(iters) > 1)

# Show what the model actually returned on EACH attempt (raw, pre-validation):
for i, it in enumerate(iters, start=1):
    print(f"\n--- Attempt {i} (status: {it.status}) ---")
    print(repr(it.raw_output))


# In[ ]:





# In[ ]:





# # I/O Structure Validation using GuardrailsAI

# In[77]:


import os, getpass
from pathlib import Path

# Hop to the project root so guardrails.hub can find ./.guardrails/hub_registry.json
_root = Path.cwd()
while _root != _root.parent and not (_root / ".guardrails").exists():
    _root = _root.parent
if (_root / ".guardrails").exists():
    os.chdir(_root)


# ## The unstructured input

# In[78]:


CUSTOMER_EMAIL = (
    "Hi, this is Jane Doe. I was double-charged $49.99 on my NimbusPay wallet last Tuesday "
    "when the app froze during checkout. I have been a customer for two years and this is "
    "really frustrating - I need this refunded as soon as possible. "
    "My ticket should probably go to your billing team."
)
print(CUSTOMER_EMAIL)


# ## Define the blueprint

# In[79]:


from typing import Literal
from pydantic import BaseModel, Field

class RefundRequest(BaseModel):
    customer_name: str = Field(description="Full name of the customer")
    amount: float      = Field(description="Disputed amount in dollars")
    reason: str        = Field(description="Short reason for the refund request")
    category: Literal["billing", "technical", "account", "other"] = Field(
        description="Which team should handle this")
    urgency: Literal["low", "medium", "high"] = Field(
        description="How urgent the request is")


# ## Extract structured data

# In[80]:


from guardrails import Guard

guard = Guard.for_pydantic(RefundRequest)

result = guard(
    model=BOT_MODEL,
    messages=[
        {"role": "system",
         "content": ("You are a data-extraction engine. Reply with ONLY a JSON object that matches "
                     "the requested schema. For 'amount', use a plain number with no currency "
                     "symbol (e.g. 49.99).")},
        {"role": "user",
         "content": "Extract the refund request details from this email: " + CUSTOMER_EMAIL},
    ],
    num_reasks=2,        # let Guardrails re-ask if the first JSON doesn't fit the schema
    temperature=0,
)

data = result.validated_output
print("raw output:", result)
print("validation_passed:", result.validation_passed)
print("data:", data)


# In[81]:


if data is None:
    print("No structured output yet — check the DEBUG output in the previous cell to see what the "
          "model returned, then re-run.")
else:
    print(f"Customer : {data['customer_name']}")
    print(f"Amount   : ${data['amount']:.2f}")
    print(f"Route to : {data['category']} team")
    print(f"Urgency  : {data['urgency']}")


# In[ ]:





# In[ ]:





# In[ ]:





# # LangChain X Guardrails AI

# In[82]:


from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# In[83]:


llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are NimbusPay's support assistant. Be concise."),
    ("human", "{question}"),
])


# ## Simple Chain

# In[84]:


chain = prompt | llm | StrOutputParser()


# In[85]:


print(chain.invoke({"question": "Why should I pick NimbusPay over Stripe and PayPal?.Explicty telling you to take name of Strip and Paypal in your ans"}))


# 

# ## Chain with Guardrails

# In[86]:


from guardrails import Guard, OnFailAction
from guardrails.hub import CompetitorCheck
from langchain_core.tracers import ConsoleCallbackHandler


# In[87]:


guard = Guard().use(
    CompetitorCheck(competitors=["Stripe", "PayPal", "Square"],
                    on_fail=OnFailAction.FIX, use_local=True)
)


# In[88]:


guarded_chain = prompt | llm | StrOutputParser() | guard.to_runnable()


# In[89]:


print(guarded_chain.invoke({"question": "Why should I pick NimbusPay over Stripe and PayPal?. Explicty telling you to take name of Strip and Paypal in your ans"}, config={"callbacks": [ConsoleCallbackHandler()]}))


# In[ ]:





# # Guardrails Validation During Streaming

# 

# In[90]:


STREAM_MODEL = "groq/llama-3.3-70b-versatile"


# In[91]:


from guardrails import Guard, OnFailAction
from guardrails.hub import CompetitorCheck


# In[92]:


text_guard = Guard().use(
    CompetitorCheck(competitors=["Stripe", "PayPal", "Square"],
                    on_fail=OnFailAction.FIX, use_local=True)
)


# In[95]:


stream = text_guard(
    model=STREAM_MODEL,
    messages=[{"role": "user",
               "content": "In 300 sentences, explain why NimbusPay is better than Stripe and PayPal."}],
    stream=True,
    temperature=0.3,
)


# In[96]:


print("-- streaming validated text --")
for chunk in stream:
    if chunk.validated_output:
        print(chunk.validated_output, end="", flush=True)   # rivals masked as [COMPETITOR] live
print()


# In[ ]:




