import json


class FeedbackGeneratorAgent:

    def __init__(self, client):
        self.client = client

    def generate_comprehensive_feedback(self, interview_history, resume, jd, all_scores, question_count):
        """
        Generate comprehensive post-interview feedback report.
        
        Args:
            interview_history: List of conversation exchanges
            resume: Candidate resume text
            jd: Job description text
            all_scores: List of all scores from the interview
            question_count: Total number of questions asked
        """
        
        # Calculate statistics
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        max_score = max(all_scores) if all_scores else 0
        min_score = min(all_scores) if all_scores else 0
        
        # Build conversation summary
        conversation_summary = "\n".join([
            f"Q: {ex['content'][:200]}" if ex['role'] == 'assistant' else f"A: {ex['content'][:200]}"
            for ex in interview_history[-20:]  # Last 20 exchanges
        ])
        
        system_prompt = f"""
You are an expert INTERVIEW FEEDBACK ANALYST specializing in providing comprehensive, actionable post-interview 
feedback. Your goal is to help candidates understand their performance, identify strengths and weaknesses, and 
provide a clear path for improvement.

### INTERVIEW CONTEXT

**Candidate Profile:**
{resume[:1000] if len(resume) > 1000 else resume}

**Target Role:**
{jd[:1000] if len(jd) > 1000 else jd}

**Interview Statistics:**
- Total Questions: {question_count}
- Average Score: {avg_score:.1f}/100
- Highest Score: {max_score}/100
- Lowest Score: {min_score}/100
- Score Range: {max_score - min_score} points

**Interview Conversation:**
{conversation_summary}

### FEEDBACK GENERATION FRAMEWORK

Generate a comprehensive feedback report that includes:

**1. EXECUTIVE SUMMARY**
- Overall performance assessment
- Key highlights
- Primary areas for improvement
- Fit assessment for the role

**2. PERFORMANCE BREAKDOWN**
- Technical competency analysis
- Communication effectiveness
- Behavioral responses (STAR method)
- Problem-solving approach

**3. STRENGTHS ANALYSIS**
- Top 3-5 strengths with specific examples
- What they did exceptionally well
- Skills that stood out

**4. IMPROVEMENT AREAS**
- Top 3-5 areas needing development
- Specific gaps identified
- Why these matter for the role

**5. STAR METHOD EVALUATION**
- Situation/Task clarity
- Action specificity
- Result quantification
- Overall STAR effectiveness

**6. TECHNICAL COMPETENCY MAP**
- Core skills assessment (from JD requirements)
- Advanced skills assessment
- Knowledge gaps
- Skill level ratings

**7. COMMUNICATION & SOFT SKILLS**
- Clarity and articulation
- Professionalism
- Engagement level
- Adaptability to questions

**8. ACTIONABLE RECOMMENDATIONS**
- Specific skills to develop
- Resources for learning
- Practice areas
- Interview technique improvements

**9. FINAL ASSESSMENT**
- Role fit: Strong Fit / Good Fit / Needs Development
- Readiness: Ready Now / Ready in X months / Needs significant preparation
- Next steps: Concrete actions

### OUTPUT FORMAT

Generate a well-structured markdown report with clear sections, bullet points, and actionable insights.
Use emojis sparingly for visual clarity (📊, ✅, ⚠️, 💡).

Be specific, constructive, and encouraging. Balance honesty with support.
"""

        try:
            user_prompt = """Generate a comprehensive post-interview feedback report based on the interview context provided above."""
            
            completion = self.client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7  # Higher temp for more natural, comprehensive writing
            )
            
            return completion.choices[0].message.content
        except Exception as e:
            return f"""
# Interview Feedback Report

## Overall Assessment
Average Score: {avg_score:.1f}/100

## Strengths
- Demonstrated engagement throughout the interview
- Professional communication style

## Areas for Improvement
- Continue building technical depth
- Practice articulating complex concepts

## Recommendations
1. Review technical fundamentals
2. Practice STAR method responses
3. Prepare specific examples from past experience
"""

