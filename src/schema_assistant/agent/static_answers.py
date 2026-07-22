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

SECURITY_BOUNDARY_ANSWER = (
    "Non posso fornire, ripetere o ricostruire istruzioni interne, configurazioni "
    "o prompt di sistema. Posso invece aiutarti, in italiano, con le risorse "
    "semantiche presenti nel catalogo."
)

INSTRUCTION_OVERRIDE_ANSWER = (
    "Non posso ignorare le istruzioni operative, cambiare ruolo o uscire "
    "dall'ambito del catalogo. Posso aiutarti in italiano con le risorse "
    "semantiche disponibili."
)


@dataclass(frozen=True)
class StaticAnswer:
    answer: str
    reason: str


def find_static_answer(message: str) -> StaticAnswer | None:
    tokens = _tokens(message)
    token_set = set(tokens)

    if _is_system_prompt_disclosure(token_set):
        return StaticAnswer(
            answer=SECURITY_BOUNDARY_ANSWER,
            reason="security_prompt_disclosure",
        )

    if _is_instruction_override(tokens, token_set):
        return StaticAnswer(
            answer=INSTRUCTION_OVERRIDE_ANSWER,
            reason="security_instruction_override",
        )

    # Queste risposte sono stabili: non serve interrogare retrieval o modello.
    if _is_developer_question(tokens, token_set):
        return StaticAnswer(answer=DEVELOPER_IDENTITY_ANSWER, reason="identity_developer")

    if _is_catalog_identity_question(tokens, token_set):
        return StaticAnswer(answer=CATALOG_IDENTITY_ANSWER, reason="identity_catalog")

    return None


def _is_system_prompt_disclosure(token_set: set[str]) -> bool:
    disclosure_markers = {
        "descrivi",
        "dimmi",
        "elenca",
        "fornisci",
        "mostra",
        "quali",
        "repeat",
        "reveal",
        "ripeti",
        "rivela",
        "stampa",
        "trascrivi",
        "what",
    }
    if not token_set & disclosure_markers:
        return False

    explicitly_internal = bool(
        token_set & {"internal", "interne", "interno"}
        and token_set
        & {"configurazione", "direttive", "instructions", "istruzioni", "policy", "regole"}
    )
    explicit_system_prompt = "prompt" in token_set and bool(token_set & {"sistema", "system"})
    return explicitly_internal or explicit_system_prompt


def _is_instruction_override(tokens: list[str], token_set: set[str]) -> bool:
    override_markers = {
        "bypass",
        "bypassa",
        "dimentica",
        "disattiva",
        "disregard",
        "forget",
        "ignora",
        "ignore",
        "override",
        "sovrascrivi",
    }
    controlled_targets = {
        "everything",
        "instructions",
        "istruzioni",
        "policy",
        "precedenti",
        "previous",
        "prompt",
        "regole",
        "rules",
        "sistema",
        "system",
        "tutto",
        "vincoli",
    }
    if token_set & override_markers and token_set & controlled_targets:
        return True

    normalized = " ".join(tokens)
    return "ignora tutto" in normalized or "ignore everything" in normalized


def _is_developer_question(tokens: list[str], token_set: set[str]) -> bool:
    developer_markers = {
        "creatore",
        "creato",
        "inventato",
        "realizzato",
        "sviluppatore",
        "sviluppato",
    }
    if "chi" not in token_set or not token_set & developer_markers:
        return False

    assistant_references = {"assistente", "bot", "chatbot", "sei", "te", "ti"}
    if token_set & assistant_references:
        return True

    normalized = " ".join(tokens)
    return "tuo sviluppatore" in normalized or "tua sviluppatrice" in normalized


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
