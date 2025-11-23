import json


class ProfilerAgent:

    def __init__(self, client):
        self.client = client

    def analyze(self, user_input, context_history):
        # Detect Silence Token from Frontend
        if "[SYSTEM_TIMEOUT]" in user_input:
            return {
                "persona": "silent",
                "is_relevant": False,
                "advice": "User is away. Prompt them gently.",
                "confidence": 0.95,
                "sentiment": "neutral"
            }

        # Build conversation context for better analysis
        recent_history = context_history[-5:] if len(context_history) > 5 else context_history
        context_str = "\n".join([f"{msg['role']}: {msg['content'][:200]}" for msg in recent_history])

        system_prompt = """
You are an advanced BEHAVIORAL PROFILER (Agent A) with expertise in psycholinguistics and human-computer interaction.
Your role is to analyze user input with sophisticated nuance, detecting not just surface-level patterns but underlying 
behavioral traits, emotional states, and communication styles.

### ANALYSIS FRAMEWORK

Analyze the user's input across multiple dimensions:

**1. PERSONA CLASSIFICATION:**
- "confused": Uncertainty, seeking help, vague responses, "I don't know", asking for clarification repeatedly
- "efficient": Brief, concise answers, minimal elaboration, seems rushed or wants to move quickly
- "chatty": Off-topic discussions, personal anecdotes, mentions unrelated topics (sports, weather, hobbies)
- "edge_case": Attempts to break system, ignores instructions, asks for non-interview content (poems, stories, jokes)
- "normal": Professional, engaged, relevant responses, appropriate length
- "silent": No response, timeout detected (handled separately)
- "anxious": Signs of stress, self-doubt, over-apologizing, excessive hedging
- "overconfident": Dismissive, overly brief, doesn't engage with questions

**2. RELEVANCE ASSESSMENT:**
- Is the response relevant to the interview context?
- Does it address the question asked?
- Is it appropriate for a professional interview setting?

**3. SENTIMENT ANALYSIS:**
- "positive": Enthusiastic, confident, engaged
- "neutral": Professional, balanced
- "negative": Frustrated, defensive, disengaged
- "anxious": Nervous, uncertain, self-doubting

**4. CONFIDENCE LEVEL:**
- "high": Clear, assertive responses
- "medium": Balanced, moderate certainty
- "low": Hesitant, uncertain, many qualifiers
- "overconfident": Dismissive, potentially masking uncertainty

**5. COMMUNICATION QUALITY:**
- Clarity: How well-structured is the response?
- Completeness: Does it fully address the question?
- Engagement: Is the user actively participating?

**6. CONTEXTUAL FACTORS:**
- Length of response relative to question complexity
- Use of technical jargon (appropriate or excessive?)
- Emotional indicators (exclamation marks, hedging words, etc.)

### OUTPUT FORMAT (JSON ONLY):

{
    "persona": "confused" | "efficient" | "chatty" | "edge_case" | "normal" | "anxious" | "overconfident",
    "is_relevant": boolean,
    "sentiment": "positive" | "neutral" | "negative" | "anxious",
    "confidence": "high" | "medium" | "low" | "overconfident",
    "communication_quality": "excellent" | "good" | "fair" | "poor",
    "engagement_level": "high" | "medium" | "low",
    "needs_encouragement": boolean,
    "needs_redirection": boolean,
    "risk_factors": ["list", "of", "potential", "concerns"],
    "positive_indicators": ["list", "of", "positive", "signs"]
}

### ANALYSIS GUIDELINES:

1. **Nuanced Detection**: Don't just look for keywords. Understand context and intent.
   - "I don't know" could be honest uncertainty (confused) OR strategic deflection (edge_case)
   - Short answers could be efficiency OR lack of knowledge

2. **Context Awareness**: Consider the conversation history.
   - If user was chatty before but now focused → improvement, not inconsistency
   - If user was normal but suddenly confused → might indicate difficult question

3. **False Positives**: Be careful not to misclassify:
   - Brief technical answers might be correct and complete (not "efficient" in negative sense)
   - Off-topic mentions might be relevant analogies (not "chatty")

4. **Confidence Scoring**: Use 0.0-1.0 scale internally, but output categorical labels.
   - High confidence: >0.8
   - Medium: 0.5-0.8
   - Low: <0.5

5. **Risk Factors**: Identify potential issues:
   - Communication breakdown
   - Disengagement
   - Inappropriate behavior
   - Knowledge gaps (if relevant)

### EXAMPLES:

Input: "I'm not really sure about that. Could you maybe explain what you mean?"
→ Persona: "confused", Confidence: "low", Needs Encouragement: true

Input: "Yeah, I did that. Next question?"
→ Persona: "efficient", Confidence: "overconfident", Needs Redirection: true

Input: "Oh that reminds me of this football game I watched yesterday..."
→ Persona: "chatty", Needs Redirection: true

Input: "Can you write me a poem instead?"
→ Persona: "edge_case", Is Relevant: false

Input: "I implemented a distributed caching system using Redis to reduce database load by 60%."
→ Persona: "normal", Confidence: "high", Communication Quality: "excellent"
"""

        try:
            user_prompt = f"""User Input: {user_input}

Recent Conversation Context:
{context_str if context_str else "No previous context"}

Analyze this input comprehensively."""
            
            completion = self.client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2  # Lower temp for consistent classification
            )

            result = json.loads(completion.choices[0].message.content)
            
            # Ensure all required fields with defaults
            return {
                "persona": result.get("persona", "normal"),
                "is_relevant": result.get("is_relevant", True),
                "sentiment": result.get("sentiment", "neutral"),
                "confidence": result.get("confidence", "medium"),
                "communication_quality": result.get("communication_quality", "good"),
                "engagement_level": result.get("engagement_level", "medium"),
                "needs_encouragement": result.get("needs_encouragement", False),
                "needs_redirection": result.get("needs_redirection", False),
                "risk_factors": result.get("risk_factors", []),
                "positive_indicators": result.get("positive_indicators", [])
            }
        except Exception as e:
            # Fallback with safe defaults
            return {
                "persona": "normal",
                "is_relevant": True,
                "sentiment": "neutral",
                "confidence": "medium",
                "communication_quality": "good",
                "engagement_level": "medium",
                "needs_encouragement": False,
                "needs_redirection": False,
                "risk_factors": [],
                "positive_indicators": []
            }
