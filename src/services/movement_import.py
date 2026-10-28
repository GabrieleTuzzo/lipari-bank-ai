# src/services/movement_import.py — il CSV riga per riga: ogni riga importata o spiegata
import csv

from pydantic import ValidationError

from src.exceptions import InvalidFileError
from src.types.error import ValidationDetail
from src.types.movements import ImportProblem, ImportResult, MovementRow
from src.validation import dettaglio_validazione, valore_ricevuto

INTESTAZIONE = ["date", "description", "amount", "currency"]


def motivo(errore: ValidationError) -> ValidationDetail:
    """Converte il primo errore Pydantic nello stesso dettaglio leggibile usato dall'API."""
    return dettaglio_validazione(errore.errors()[0])


def importa_csv(contenuto: bytes) -> ImportResult:
    if not contenuto.strip():
        raise InvalidFileError("Il file è vuoto")
    try:
        testo = contenuto.decode("utf-8-sig")  # -sig: toglie il BOM che Excel mette in testa
    except UnicodeDecodeError:
        raise InvalidFileError("Il file non è testo UTF-8: non è un CSV") from None

    # Un movimento per riga del file, e ogni riga si legge da sola: una virgoletta aperta e mai
    # chiusa, o un campo oltre il limite del modulo csv, rovinano la loro riga e non le successive
    righe = [r.rstrip("\r") for r in testo.split("\n")]
    if next(csv.reader(righe[:1]), []) != INTESTAZIONE:
        raise InvalidFileError(f"L'intestazione deve essere {','.join(INTESTAZIONE)}")

    importate, problemi = 0, []
    for numero, linea in enumerate(righe[1:], start=2):  # la riga nel file: la 1 è l'intestazione
        if not linea.strip():
            continue  # una riga vuota non è un movimento
        try:
            campi = next(csv.reader([linea], strict=True))
        except csv.Error:  # sollevato nel codice: se nessuno lo cattura, è un 500
            problemi.append(
                ImportProblem(
                    row=numero,
                    field="riga",
                    message="Riga CSV non leggibile",
                    received=valore_ricevuto(linea, ""),
                    expected="riga CSV valida con quattro campi",
                )
            )
            continue
        if len(campi) != len(INTESTAZIONE):
            problemi.append(
                ImportProblem(
                    row=numero,
                    field="riga",
                    message="Numero di campi errato",
                    received=f"{len(campi)} campi",
                    expected="quattro campi: date, description, amount, currency",
                )
            )
            continue
        try:
            MovementRow.model_validate(dict(zip(INTESTAZIONE, campi, strict=True)))
        except ValidationError as e:  # costruito nel codice: se nessuno lo cattura, è un 500
            problemi.append(ImportProblem(row=numero, **motivo(e).model_dump()))
            continue
        importate += 1
    return ImportResult(imported_count=importate, problems=problemi)
