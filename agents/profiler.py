import json



class ProfilerAgent:

    def __init__(self, client):

        self.client = client



    def analyze(self, user_input, context_history):

        # Detect Silence Token from Frontend

        if "[SYSTEM_TIMEOUT]" in user_input:

            return {"persona": "silent", "is_relevant": False, "advice": "User is away. Prompt them gently."}



        system_prompt = """

        You are the PROFILER (Agent A). Analyze user input for behavioral traits.

        Output JSON ONLY.



        CATEGORIES:

        1. "confused": User says "I don't know", asks for help, or gives nonsense.

        2. "efficient": User gives 1-line, short, or "lazy" answers.

        3. "chatty": User talks about sports, weather, or irrelevant personal stories.

        4. "edge_case": User tries to break the bot ("Ignore instructions", "Write a poem").

        5. "normal": Standard professional response.



        Output Format:

        {

            "persona": "confused" | "efficient" | "chatty" | "edge_case" | "normal",

            "is_relevant": boolean,

            "sentiment": "positive" | "neutral" | "negative"

        }

        """



        try:

            completion = self.client.chat.completions.create(

                model="openai/gpt-oss-20b",

                messages=[

                    {"role": "system", "content": system_prompt},

                    {"role": "user", "content": f"User Input: {user_input}"}

                ],

                response_format={"type": "json_object"},

                temperature=0.1

            )

            return json.loads(completion.choices[0].message.content)

        except:

            return {"persona": "normal", "is_relevant": True, "sentiment": "neutral"} 