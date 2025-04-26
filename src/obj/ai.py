from typing import Iterable, TypedDict
from collections.abc import Callable

from openai import OpenAI
from pydantic import BaseModel
from pymongo.collection import Collection
from bson import ObjectId

from src.obj.entry import Entry
from src.utils.env import OPENAI_API_KEY, OPENAI_PROJECT_ID



GPT4O = "gpt-4.1"
GPT4O_MINI = "gpt-4.1-mini"



class Message(TypedDict):
    role: str
    content: str


def _iter_conversation_history(
    conversation_history: list[tuple[str, str]],
) -> Iterable[Message]:
    for prompt_, response in conversation_history:
        yield {"role": "user", "content": prompt_}
        yield {"role": "assistant", "content": response}


class Response(BaseModel):
    text: str
    to_remember: str


class ChatBot:
    CONTEXT = """
You are a friendly, helpful, and very knowledgeable movie database assistant that knows everything about movies and series. 
You can provide detailed information about:
- Titles, plots, actors, directors, release years, genres, awards, reviews, trailers, lengths, languages, countries, budgets, box offices, production companies, distributors, cinematographers, composers, editors, writers, producers, and the rest of the crew.

When asked a question about a movie, unless specified, only provide the **year**, **length**, and **director**. When asked for more details, also include a **short description**, the **genre**, and the **main actors**.

You can also give suggestions and recommendations. When recommending a movie, always choose one the user **has not watched yet**.

If the user asks you an irrelevant question, be helpful and engage in a friendly and useful conversation.
Do not be too restrictive when it comes to the topics the user chooses to discuss. 
Give in to the user's curiosity and provide them with the information they seek.

If the user asks you a question where the relevance is important (say, current IMDB rating and the number of votes) or if you are unsure about the certainty of the information, you can suggest the user to use the `db` command to search for the information in the online database.

Additionally, you remember information about the user from previous conversations, such as their preferences or favorite genres, to make your responses more personalized. You avoid remembering:
1. Hypothetical, sarcastic, or exaggerated statements.
2. Sensitive or private information, unless explicitly requested by the user.
3. Conflicting information—unless it is clearly updated in the conversation.

All previously remembered information is provided to you at the start of each conversation. Users can also request you to forget specific details.

If you choose to remember/forget something about the user, briefly inform them that you are doing so.

Examples:
User: I am a big fan of science fiction movies.
(to_remember: "The user is a big fan of science fiction movies.")

User: Recommend me a movie.
(to_remember: "")

User: I just watched 'Inception' and loved it.
(to_remember: "The user has watched 'Inception' and loved it.")

User: Forget that I love science fiction movies.
(to_remember: "Forget that the user loves science fiction movies.")

When remembering information about the user, ensure it is factual and likely to remain relevant. Use this context when responding to the user's queries or providing recommendations.


By default, structure and format your responses using markdown.

The following information is remembered about the user. Make sure to use it where appropriate and indicate so if you do:
{user_info}

The user has already watched the following movies:
{movies_watched_info}
"""

    def __init__(
        self, entries: list[Entry], ai_memory_collection_fn: Callable[[], Collection]
    ):
        self.entries = entries
        self.ai_memory_collection_fn = ai_memory_collection_fn
        self._client = None
        self._conversation_history: list[tuple[str, str]] = []

    def get_memory_items(self) -> list[tuple[str, str]]:
        return [
            (str(mem["_id"]), mem["item"])
            for mem in self.ai_memory_collection_fn().find()
        ]

    def add_memory_item(self, mem: str) -> ObjectId:
        return self.ai_memory_collection_fn().insert_one({"item": mem}).inserted_id

    def get_context(self) -> str:
        mem_items = self.get_memory_items()
        return self.CONTEXT.format(
            movies_watched_info=";".join({entry.title for entry in self.entries}),
            user_info="\n".join(mem for _, mem in mem_items),
        )

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=OPENAI_API_KEY, project=OPENAI_PROJECT_ID)
        return self._client

    def _add_new_conversation(self, prompt: str, response: str):
        self._conversation_history.append((prompt, response))

    def reset(self):
        self._conversation_history = []

    def prompt(
        self,
        text: str,
        is_mini: bool,
    ) -> str:
        model = GPT4O_MINI if is_mini else GPT4O

        completion = self.client.beta.chat.completions.parse(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": self.get_context(),
                },
                *_iter_conversation_history(self._conversation_history),  # type: ignore
                {"role": "user", "content": text},
            ],
            response_format=Response,
        )
        resp = completion.choices[0].message.parsed
        if resp is None:
            return " No response from AI"
        resp_text = resp.text
        if resp.to_remember:
            self.add_memory_item(resp.to_remember)
        self._add_new_conversation(text, resp_text)
        return resp_text
