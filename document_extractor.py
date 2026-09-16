
import io
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path

from PIL import Image
import pytesseract
from pypdf import PdfReader
from pdf2image import convert_from_path


SUPPLIER_RULES = [
    ("EDP", ["edp comercial", "edp"]),
    ("Endesa", ["endesa"]),
    ("Goldenergy", ["goldenergy"]),
    ("MEO", ["meo", "moche"]),
    ("NOS", ["nos comunica", "nos"]),
    ("Vodafone", ["vodafone"]),
    ("DIGI", ["digi"]),
    ("Continente", ["continente", "modelo continente"]),
    ("Pingo Doce", ["pingo doce"]),
    ("Lidl", ["lidl"]),
    ("Auchan", ["auchan", "jumbo"]),
    ("Mercadona", ["mercadona"]),
    ("Galp", ["galp"]),
    ("Repsol", ["repsol"]),
    ("BP", ["bp portugal", " bp "]),
    ("Netflix", ["netflix"]),
    ("Spotify", ["spotify"]),
]

CATEGORY_RULES = {
    "Eletricidade": ["edp", "endesa", "goldenergy", "eletricidade", "energia"],
    "Telecomunicações": ["meo", "nos", "vodafone", "digi", "internet", "telecom"],
    "Alimentação": ["continente", "pingo doce", "lidl", "auchan", "mercadona", "supermercado"],
    "Combustível": ["galp", "repsol", "bp portugal", "combustível", "gasolina", "gasóleo"],
    "Subscrições": ["netflix", "spotify", "disney", "prime video", "hbo", "subscrição"],
    "Água": ["água", "aguas de gaia", "águas de gaia"],
    "Gás": ["gás natural", "gas natural"],
}

SUPPLIER_SPECIFIC_RULES = {
    "EDP": {
        "total_patterns": [
            r"(?:Total a pagar|Valor a pagar)\s*[: ]+\s*([0-9\.\s]+,[0-9]{2})"
        ],
        "date_patterns": [
            r"(?:Data limite|Data de emissão)\s*[: ]+\s*(\d{2}[/-]\d{2}[/-]\d{4})"
        ],
    },
    "MEO": {
        "total_patterns": [
            r"(?:Total a pagar|Total)\s*[: ]+\s*([0-9\.\s]+,[0-9]{2})"
        ],
    },
    "Vodafone": {
        "total_patterns": [
            r"(?:Total a pagar|Total da fatura)\s*[: ]+\s*([0-9\.\s]+,[0-9]{2})"
        ],
    },
    "Continente": {
        "total_patterns": [
            r"(?:TOTAL|TOTAL EUR)\s*[: ]*\s*([0-9\.\s]+,[0-9]{2})"
        ],
    },
}

DATE_PATTERNS = [
    r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b",
    r"\b(\d{4})[/-](\d{2})[/-](\d{2})\b",
]

NIF_PATTERNS = [
    r"\b(?:NIF|NIPC|Contribuinte|VAT)\s*[:#]?\s*(\d{9})\b",
    r"\b(\d{9})\b",
]

DOC_NUMBER_PATTERNS = [
    r"(?:Fatura|Factura|FT|FAT|Documento)\s*(?:n[ºo.]?|número)?\s*[:#]?\s*([A-Z0-9\-\/\.]+)",
]

TOTAL_PATTERNS = [
    r"(?:Total a pagar|Total\s*EUR|Total\s*€|TOTAL)\s*[: ]+\s*([0-9\.\s]+,[0-9]{2})",
    r"(?:Valor total|Importe total)\s*[: ]+\s*([0-9\.\s]+,[0-9]{2})",
]

VAT_PATTERNS = [
    r"(?:IVA|VAT)\s*(?:Total)?\s*[: ]+\s*([0-9\.\s]+,[0-9]{2})",
]


def normalize_text(text):
    return re.sub(r"[ \t]+", " ", text or "").strip()


def file_sha256(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_money(value):
    if not value:
        return None
    cleaned = value.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except Exception:
        return None


def validate_portuguese_nif(nif):
    nif = re.sub(r"\D", "", nif or "")
    if len(nif) != 9:
        return False
    if nif[0] not in "1235689":
        return False
    try:
        total = sum(int(nif[i]) * (9 - i) for i in range(8))
        check = 11 - (total % 11)
        if check >= 10:
            check = 0
        return check == int(nif[8])
    except Exception:
        return False


def extract_pdf_text(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        chunks = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        return "\n".join(chunks).strip()
    except Exception:
        return ""


def ocr_image_file(image_path):
    img = Image.open(image_path)
    return pytesseract.image_to_string(img, lang="por+eng")


def ocr_pdf_file(pdf_path, dpi=220, max_pages=5):
    pages = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=max_pages)
    return "\n".join(
        pytesseract.image_to_string(img, lang="por+eng")
        for img in pages
    ).strip()


def extract_document_text(file_path, extension):
    extension = extension.lower()
    text = ""
    method = "unknown"

    if extension == ".pdf":
        direct = extract_pdf_text(file_path)
        if len(normalize_text(direct)) >= 80:
            text = direct
            method = "pdf_text"
        else:
            text = ocr_pdf_file(file_path)
            method = "ocr_pdf"
    elif extension in [".jpg", ".jpeg", ".png"]:
        text = ocr_image_file(file_path)
        method = "ocr_image"

    return normalize_text(text), method


def detect_supplier(text, learned_rules=None):
    lower = f" {text.lower()} "

    if learned_rules:
        for rule in learned_rules:
            supplier = rule.get("supplier_name")
            tokens = rule.get("match_tokens") or []
            if supplier and any(token.lower() in lower for token in tokens):
                return supplier, 0.98, "learned"

    for supplier, tokens in SUPPLIER_RULES:
        if any(token in lower for token in tokens):
            return supplier, 0.95, "builtin"

    lines = [x.strip() for x in text.splitlines() if x.strip()]
    fallback = lines[0][:180] if lines else None
    return fallback, (0.45 if fallback else 0.0), "fallback"


def detect_nif(text):
    for pattern in NIF_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = m.group(1)
            valid = validate_portuguese_nif(value)
            return value, (0.98 if valid else 0.55), valid
    return None, 0.0, False


def detect_date(text, supplier=None):
    patterns = []
    if supplier in SUPPLIER_SPECIFIC_RULES:
        patterns.extend(SUPPLIER_SPECIFIC_RULES[supplier].get("date_patterns", []))
    patterns.extend(DATE_PATTERNS)

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue

        raw = m.group(1) if len(m.groups()) == 1 else None
        try:
            if raw:
                d, mo, y = re.split(r"[/-]", raw)
                return datetime(int(y), int(mo), int(d)).date(), 0.95

            if len(m.group(1)) == 4:
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return dt.date(), 0.9
        except Exception:
            pass
    return None, 0.0


def detect_document_number(text):
    for pattern in DOC_NUMBER_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)[:100], 0.9
    return None, 0.0


def detect_total(text, supplier=None):
    patterns = []
    if supplier in SUPPLIER_SPECIFIC_RULES:
        patterns.extend(SUPPLIER_SPECIFIC_RULES[supplier].get("total_patterns", []))
    patterns.extend(TOTAL_PATTERNS)

    weighted = []
    for idx, pattern in enumerate(patterns):
        for m in re.finditer(pattern, text, re.IGNORECASE):
            value = parse_money(m.group(1))
            if value is not None:
                confidence = 0.97 if supplier in SUPPLIER_SPECIFIC_RULES and idx < len(SUPPLIER_SPECIFIC_RULES[supplier].get("total_patterns", [])) else 0.9
                weighted.append((value, confidence))

    if weighted:
        value, confidence = max(weighted, key=lambda x: x[0])
        return value, confidence

    generic = re.findall(r"\b([0-9]{1,4}(?:\.[0-9]{3})*,[0-9]{2})\s*€", text)
    values = [parse_money(x) for x in generic]
    values = [x for x in values if x is not None]
    if values:
        return max(values), 0.55

    return None, 0.0


def detect_vat(text):
    vals = []
    for pattern in VAT_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            value = parse_money(m.group(1))
            if value is not None:
                vals.append(value)
    return (max(vals), 0.75) if vals else (None, 0.0)


def suggest_category_name(text, supplier, learned_rules=None):
    lower = f"{supplier or ''} {text}".lower()

    if learned_rules:
        for rule in learned_rules:
            supplier_name = (rule.get("supplier_name") or "").lower()
            category_name = rule.get("category_name")
            if supplier_name and supplier and supplier_name == supplier.lower() and category_name:
                return category_name, 0.98, "learned"

    for category, keywords in CATEGORY_RULES.items():
        if any(k in lower for k in keywords):
            return category, 0.92, "builtin"

    return "Outros", 0.35, "fallback"


def extract_fields(text, learned_rules=None):
    supplier, supplier_conf, supplier_source = detect_supplier(text, learned_rules)
    tax_id, nif_conf, nif_valid = detect_nif(text)
    doc_number, doc_conf = detect_document_number(text)
    doc_date, date_conf = detect_date(text, supplier)
    total, total_conf = detect_total(text, supplier)
    vat, vat_conf = detect_vat(text)
    category, cat_conf, cat_source = suggest_category_name(text, supplier, learned_rules)

    field_confidence = {
        "supplier": round(supplier_conf * 100, 1),
        "tax_id": round(nif_conf * 100, 1),
        "document_number": round(doc_conf * 100, 1),
        "document_date": round(date_conf * 100, 1),
        "total": round(total_conf * 100, 1),
        "vat": round(vat_conf * 100, 1),
        "category": round(cat_conf * 100, 1),
    }

    weighted = {
        "supplier": 20,
        "tax_id": 15,
        "document_number": 10,
        "document_date": 15,
        "total": 25,
        "vat": 5,
        "category": 10,
    }

    overall = sum((field_confidence[k] / 100) * weighted[k] for k in weighted)

    return {
        "supplier": supplier,
        "tax_id": tax_id,
        "tax_id_valid": nif_valid,
        "document_number": doc_number,
        "document_date": doc_date,
        "total": total,
        "vat": vat,
        "category": category,
        "confidence": round(overall, 1),
        "field_confidence": field_confidence,
        "supplier_source": supplier_source,
        "category_source": cat_source,
    }


# ============================================================
# V1.9 — Extração de linhas/produtos
# ============================================================

ITEM_CATEGORY_RULES = {
    "Alimentação": [
        "leite","pão","arroz","massa","atum","carne","frango","peixe","iogurte",
        "queijo","fiambre","ovos","banana","maçã","laranja","café","açúcar",
        "farinha","água","sumo","cerveja","bolacha","cereais","legumes","fruta"
    ],
    "Higiene": [
        "champô","shampoo","gel banho","sabonete","desodorizante","pasta dentes",
        "dentífrico","escova dentes","papel higiénico","toalhitas","pensos",
        "lâminas","creme corpo"
    ],
    "Bebé": [
        "fralda","fraldas","toalhitas bebé","papa","leite bebé","boião",
        "chupeta","biberão"
    ],
    "Casa": [
        "detergente","lava loiça","máquina roupa","amaciante","lixívia","sacos lixo",
        "esponja","guardanapos","rolo cozinha","limpa vidros","desengordurante"
    ],
    "Saúde": [
        "paracetamol","ibuprofeno","farmácia","vitamina","medicamento"
    ],
    "Animais": [
        "ração","areia gato","snack cão","comida gato","comida cão"
    ]
}


def normalize_item_description(value):
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:220]


def suggest_item_category(description):
    lower = (description or "").lower()
    for category, keywords in ITEM_CATEGORY_RULES.items():
        if any(k in lower for k in keywords):
            return category, 0.90
    return "Outros", 0.35


def _parse_item_line(line):
    """
    Heurística genérica para talões/faturas.
    Exemplos:
      LEITE M/G 1L         0,89
      2 X IOGURTE 0,75     1,50
      DETERGENTE ROUPA     6,99
    """
    raw = normalize_item_description(line)
    if not raw or len(raw) < 4:
        return None

    # Ignorar linhas típicas de totais / cabeçalhos.
    lower = raw.lower()
    ignore_tokens = [
        "total", "subtotal", "iva", "nif", "contribuinte", "fatura", "factura",
        "data", "hora", "pagamento", "multibanco", "troco", "valor pago",
        "base incid", "taxa", "cartão", "cartao"
    ]
    if any(t in lower for t in ignore_tokens):
        return None

    # preço no fim da linha
    m = re.search(r"(.+?)\s+([0-9]{1,4}(?:\.[0-9]{3})*,[0-9]{2})\s*€?\s*$", raw)
    if not m:
        return None

    desc = normalize_item_description(m.group(1))
    total = parse_money(m.group(2))
    if not desc or total is None or total <= 0:
        return None

    quantity = 1.0
    unit_price = total

    # quantidade x preço unitário dentro da descrição
    qm = re.search(
        r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*[xX]\s*(.+?)(?:\s+([0-9]+(?:[.,][0-9]{2})))?$",
        desc
    )
    if qm:
        try:
            quantity = float(qm.group(1).replace(",", "."))
        except Exception:
            quantity = 1.0
        desc = normalize_item_description(qm.group(2))
        if qm.group(3):
            try:
                unit_price = float(qm.group(3).replace(",", "."))
            except Exception:
                unit_price = total / quantity if quantity else total
        else:
            unit_price = total / quantity if quantity else total

    category, confidence = suggest_item_category(desc)

    return {
        "description": desc,
        "quantity": round(quantity, 3),
        "unit_price": round(float(unit_price), 2),
        "line_total": round(float(total), 2),
        "suggested_category": category,
        "category_confidence": round(confidence * 100, 1)
    }


def extract_line_items(text, document_total=None):
    """
    Extrai linhas de produto de forma heurística.
    Devolve apenas itens plausíveis e um score simples de cobertura.
    """
    items = []
    seen = set()

    for line in (text or "").splitlines():
        item = _parse_item_line(line)
        if not item:
            continue

        key = (
            item["description"].lower(),
            item["quantity"],
            item["line_total"]
        )
        if key in seen:
            continue

        seen.add(key)
        items.append(item)

    items_total = round(sum(x["line_total"] for x in items), 2)

    coverage = None
    if document_total and float(document_total) > 0:
        coverage = round(min(100.0, items_total / float(document_total) * 100), 1)

    return {
        "items": items[:250],
        "items_total": items_total,
        "coverage_percent": coverage
    }
