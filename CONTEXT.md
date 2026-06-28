# Domain Glossary

## Roleplay Persona System Concepts

- **CharacterState**: The dynamic attributes of a character that evolve over time through interactions. Currently bound to a single character (Mei Wenfeng).
- **Affection (好感度)**: A dynamic attribute (0-100) representing the character's emotional attachment to the user.
- **Social Status (格局修养)**: A dynamic attribute (0-100) representing the character's outward demeanor and social standing.
- **Social Skills (为人处世)**: A dynamic attribute (0-100) representing the character's ability to handle conflicts and emotional situations.
- **Refractory Period (生理不应期)**: A dynamic attribute representing the recovery phase after an intense interaction (e.g., climax). Decays over rounds.

## Serious Teaching & Core Architecture Concepts

- **CharacterStateManager**: A deep module responsible for encapsulating all state transitions, boundary checks (e.g., 0-100 limits), and database persistence for CharacterState.
- **State Interface**: The state is represented as a strongly-typed `@dataclass` (`CharacterState`). The manager provides `get_state()` and `update_state()`.
- **Error Handling (State)**: The state manager raises explicit exceptions (`CharacterStateError`) when persistence fails, rather than failing silently or returning default mock data. Callers are responsible for handling these exceptions and providing appropriate fallbacks.
- **Side-Effect Handlers**: Extracted from routing logic into domain-specific, stateless classes (e.g., `PropertyUpdateHandler`, `CourseManagerHandler`).
- **ActionRegistry**: An application-level singleton registry that holds instances of all side-effect handlers. The `ResponsePipeline` references this registry instead of instantiating handlers per request.
- **Error Handling (Side-Effects)**: Side-effect handlers raise exceptions rather than swallowing them. The `ResponsePipeline` catches these exceptions centrally during the execution phase, logging them to prevent interrupting the chat stream, ensuring uniform error management.
