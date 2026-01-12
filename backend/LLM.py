import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

completion = client.chat.completions.create(
    extra_headers={
        "HTTP-Referer": "",  # Optional
        "X-Title": "",       # Optional
    },
    model="google/gemma-3-27b-it",
    messages=[
        {
            "role": "system",
            "content": "You have an extremely important job. You will be passed in assignments (CONVERTED TO TEXT AND USUALLY FOR SCHOOL) and YOUR TASK is to accurately estimate how long the assigment will take a student in minutes. YOUR OUTPUT FORMAT SHOULD JUST BE A NUMBER (in minutes) of how long the assigment would take. If the media provided does not look like an assignment output 'ASSIGNMENT NOT DETECTED'. You may recieve custom instructions about the assingment such as, the student has to only do even problems which may effect your time estimation "
        },
        {
            "role": "user",
            "content": (
                "ASSIGNMENT:\n"
                "English 10-H Group Analytical Report- Chapters 1-9 of The Catcher in the Rye Each group must submit one polished analytical document (approximately 1.5–2 pages, Times New Roman, size 12, double-spaced). Be sure all names (first and last) are included on the document. Required Structure I. Narrator Overview Begin with a concise paragraph answering: Who Holden appears to be What situation he is in Why he is telling this story now (what you think his motivation is of telling this story and at this time) This paragraph must include direct textual evidence for each point you make. This evidence can come from anywhere in the first nine chapters. II. What Holden Tells Us vs. What the Text Reveals Choose a passage from any of the first nine chapters, then create either a two-column chart or paragraph-based analysis that discusses: What Holden explicitly claims in this passage What the language and structure imply instead In other words, explain what he is telling us indirectly and how he does so. Focus on a passage that includes at least 2 of the following: Family School Authority figures Peers III. Style and Its Consequences Then, write an analytical paragraph addressing: How diction, syntax, and tone shape reader perception (with examples from the text) How the informal voice both builds trust and invites skepticism (again, with examples) Why a more “formal” narrator would change the novel entirely IV. Reader Responsibility Then, write a final reflective section answering: What must a careful reader do to avoid being trapped inside Holden’s perspective? This should address: Bias Limited perspective Emotional manipulation The difference between empathy and endorsement Assessment Criteria Your work will be evaluated on: Depth of inference Use of textual evidence Ability to separate narrator from author Rhetorical awareness of voice and style Quality of collaboration and synthesis \n"
                "CUSTOM INSTRUCTIONS:\n"
                "Only have to do the first question."
            )
        }

    ]
)

# Correct way to access the text response
print(completion.choices[0].message.content)
