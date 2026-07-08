import re
import unicodedata
from dataclasses import dataclass

CATALOG_IDENTITY_ANSWER = (
    "Sono l'assistente del catalogo per l'interoperabilità della semantica dei dati, "
    "che può aiutarti a conoscere le risorse semantiche pubblicate sul catalogo.\n\n"
    "Posso risponderti sulle risorse pubblicate da INPS, INAIL, ISTAT e su alcuni "
    "argomenti di semantica e di interoperabilità dei dati. Puoi ritrovare i "
    "contenuti che ti proporrò direttamente sulle pagine di schema.gov.it."
)

DEVELOPER_IDENTITY_ANSWER = (
    "Sono stato sviluppato da DXC Technology, fornitore e azienda leader globale "
    "nei servizi IT e soluzioni digitali.\n\n"
    "DXC è partner operativo di fiducia per molte delle organizzazioni più "
    "innovative al mondo, con cui collabora per sviluppare soluzioni che promuovono "
    "l'evoluzione dei settori e la crescita delle imprese.\n\n"
    "Grazie all'esperienza dei suoi professionisti in ingegneria, consulenza e "
    "tecnologia, DXC aiuta i clienti a semplificare, ottimizzare e modernizzare "
    "sistemi e processi, gestire carichi di lavoro critici e integrare "
    "l'intelligenza artificiale in modo sicuro ed efficiente. Questa competenza "
    "è alla base della mia progettazione, per offrire un'esperienza conversazionale "
    "innovativa e di qualità."
)


@dataclass(frozen=True)
class StaticAnswer:
    answer: str
    reason: str


def find_static_answer(message: str) -> StaticAnswer | None:
    tokens = _tokens(message)
    token_set = set(tokens)

    # Queste risposte sono stabili: non serve interrogare retrieval o modello.
    if _is_developer_question(token_set):
        return StaticAnswer(answer=DEVELOPER_IDENTITY_ANSWER, reason="identity_developer")

    if _is_catalog_identity_question(tokens, token_set):
        return StaticAnswer(answer=CATALOG_IDENTITY_ANSWER, reason="identity_catalog")

    return None


def _is_developer_question(token_set: set[str]) -> bool:
    return "chi" in token_set and bool(
        token_set
        & {
            "creatore",
            "creato",
            "realizzato",
            "sviluppatore",
            "sviluppato",
            "inventato",
        }
    )


def _is_catalog_identity_question(tokens: list[str], token_set: set[str]) -> bool:
    if {"chi", "sei"}.issubset(token_set):
        return True
    if {"chi", "assistente"}.issubset(token_set):
        return True
    if "presentati" in token_set:
        return True

    greeting_tokens = {"ciao", "salve", "buongiorno", "buonasera"}
    return bool(token_set & greeting_tokens) and len(tokens) <= 3


def _tokens(message: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", message.lower())
    ascii_message = normalized.encode("ascii", "ignore").decode("ascii")
    return re.findall(r"\w+", ascii_message)
