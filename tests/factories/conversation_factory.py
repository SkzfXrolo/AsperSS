from __future__ import annotations

import factory


class ConversationFactory(factory.DictFactory):
    player_name = factory.Faker("user_name")
    turns = factory.LazyFunction(
        lambda: [
            {"role": "user", "text": "hola"},
            {"role": "assistant", "text": "¿Qué necesitas?"},
            {"role": "user", "text": "como esta Mateo"},
        ]
    )
