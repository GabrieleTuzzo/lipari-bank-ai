from collections.abc import Mapping

from src.types.error import ValidationDetail

_CAMPI_ATTESI = {
    "amount": "un importo numerico maggiore di zero",
    "currency": "un codice di valuta di tre lettere maiuscole, ad esempio EUR",
    "date": "una data reale nel formato AAAA-MM-GG",
    "description": "un testo da 1 a 200 caratteri",
    "file": "un file CSV",
    "message": "un testo da 1 a 2000 caratteri",
}


def _campo(loc: object) -> str:
    if not isinstance(loc, (tuple, list)):
        return "corpo"
    parti = list(loc)
    if parti and parti[0] in ("body", "query", "path", "header", "cookie"):
        parti.pop(0)
    return ".".join(str(p) for p in parti) or "corpo"


def valore_ricevuto(valore: object, tipo: str) -> str:
    if tipo == "json_invalid":
        return "JSON non valido"
    if tipo == "missing":
        return "assente"
    if valore is None:
        return "null"
    if isinstance(valore, str):
        if not valore:
            return "vuoto"
        if not valore.strip():
            return f"solo spazi ({len(valore)} caratteri)"
        testo = valore
    elif isinstance(valore, dict):
        testo = f"oggetto con {len(valore)} campi"
    elif isinstance(valore, (list, tuple)):
        testo = f"elenco con {len(valore)} elementi"
    elif isinstance(valore, bytes):
        testo = f"dato binario ({len(valore)} byte)"
    elif isinstance(valore, (bool, int, float)):
        testo = str(valore)
    else:
        testo = type(valore).__name__
    if len(testo) > 120:
        return f"{testo[:117]}... (troncato)"
    return testo


def _aspettato(campo: str, tipo: str, errore: Mapping[str, object]) -> str:
    if campo in _CAMPI_ATTESI:
        return _CAMPI_ATTESI[campo]

    contesto = errore.get("ctx")
    if isinstance(contesto, Mapping):
        limite = contesto.get("gt")
        if tipo == "greater_than" and limite is not None:
            return f"un valore maggiore di {limite}"
        limite = contesto.get("ge")
        if tipo == "greater_than_equal" and limite is not None:
            return f"un valore maggiore o uguale a {limite}"
        limite = contesto.get("lt")
        if tipo == "less_than" and limite is not None:
            return f"un valore minore di {limite}"
        limite = contesto.get("le")
        if tipo == "less_than_equal" and limite is not None:
            return f"un valore minore o uguale a {limite}"
        limite = contesto.get("min_length")
        if tipo == "string_too_short" and limite is not None:
            return f"almeno {limite} caratteri"
        limite = contesto.get("max_length")
        if tipo == "string_too_long" and limite is not None:
            return f"al massimo {limite} caratteri"

    return {
        "json_invalid": "JSON valido",
        "missing": "un valore obbligatorio",
        "decimal_parsing": "un numero decimale",
        "float_parsing": "un numero",
        "int_parsing": "un numero intero",
        "string_pattern_mismatch": "testo nel formato richiesto",
    }.get(tipo, "un valore nel formato corretto")


def dettaglio_validazione(errore: Mapping[str, object]) -> ValidationDetail:
    tipo_valore = errore.get("type")
    tipo = tipo_valore if isinstance(tipo_valore, str) else ""
    campo = "corpo" if tipo == "json_invalid" else _campo(errore.get("loc"))
    messaggio = {
        "date_from_datetime_parsing": "Data non valida",
        "date_parsing": "Data non valida",
        "decimal_parsing": "Numero non valido",
        "float_parsing": "Numero non valido",
        "greater_than": "Valore troppo piccolo",
        "greater_than_equal": "Valore troppo piccolo",
        "int_parsing": "Numero non valido",
        "json_invalid": "Il corpo non contiene JSON valido",
        "less_than": "Valore troppo grande",
        "less_than_equal": "Valore troppo grande",
        "missing": "Campo obbligatorio mancante",
        "string_pattern_mismatch": "Formato non valido",
        "string_too_long": "Testo troppo lungo",
        "string_too_short": "Testo troppo corto",
        "string_type": "Valore non testuale",
        "value_error": "Valore non valido",
    }.get(tipo, "Valore non valido")
    if campo == "date" and tipo == "value_error":
        messaggio = "Data non valida"
    return ValidationDetail(
        field=campo,
        message=messaggio,
        received=valore_ricevuto(errore.get("input"), tipo),
        expected=_aspettato(campo, tipo, errore),
    )
