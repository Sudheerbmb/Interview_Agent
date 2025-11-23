import json



class GraderAgent:

    def __init__(self, client):

        self.client = client



    def evaluate(self, user_input, current_question, jd_text):

        system_prompt = f"""

        You are the GRADER (Agent B). Evaluate the candidate based on this JD: {jd_text[:300]}...

        Current Question: {current_question}



        CRITERIA:

        1. Score the answer (0-100).

        2. DECIDE FOLLOW-UP:

           - If answer is vague or short -> requires_followup = true.

           - If answer is detailed and correct -> requires_followup = false.



        Output JSON ONLY:

        {{

            "score": number,

            "is_correct": boolean,

            "requires_followup": boolean,

            "feedback_internal": "Brief reason for score"

        }}

        """



        try:

            completion = self.client.chat.completions.create(

                model="openai/gpt-oss-20b",

                messages=[

                    {"role": "system", "content": system_prompt},

                    {"role": "user", "content": f"Candidate Answer: {user_input}"}

                ],

                response_format={"type": "json_object"},

                temperature=0.1

            )

            return json.loads(completion.choices[0].message.content)

        except:

            return {"score": 50, "is_correct": True, "requires_followup": False}