"""Pure pt-BR Markdown renderer for ProcessingReport v0.1 (decision 0045)."""
from __future__ import annotations

import hashlib
from decimal import Decimal
from enum import Enum

from ..operation_plan.model import LengthValue
from ..processing_report import ProcessingReport, processing_report_ref
from .model import (
    HUMAN_REPORT_MEDIA_TYPE,
    HUMAN_REPORT_VERSION,
    HumanReportContractError,
    HumanReportIntegrityError,
    RenderedProcessingReport,
)


_CLASS_LABELS = {
    "body": "Corpo do texto",
    "heading": "Título/subtítulo",
    "long_quote": "Citação longa",
    "reference": "Referência",
}
_PROPERTY_LABELS = {
    "bold": "Negrito",
    "font_size": "Tamanho da fonte",
}


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise HumanReportIntegrityError("non-finite Decimal in ProcessingReport")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"-0", ""}:
        text = "0"
    return text


def _escape_text(value: str) -> str:
    if not isinstance(value, str):
        raise HumanReportIntegrityError("free text value must be str")
    value = value.replace("\\", "\\\\").replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    for char in ("`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", ".", "!", "|", ">"):
        value = value.replace(char, "\\" + char)
    return value


def _code(value: str) -> str:
    if not isinstance(value, str):
        raise HumanReportIntegrityError("machine token must be str")
    value = value.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    longest = 0
    current = 0
    for char in value:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    fence = "`" * (longest + 1)
    if value.startswith("`") or value.endswith("`"):
        return f"{fence} {value} {fence}"
    return f"{fence}{value}{fence}"


def _enum_token(value: Enum) -> str:
    token = value.value
    if not isinstance(token, str):
        raise HumanReportIntegrityError("enum token must be str")
    return _code(token)


def _value_text(value) -> str:
    if value is None:
        return "não disponível"
    if type(value) is bool:
        return "sim" if value else "não"
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, LengthValue):
        return f"{_decimal_text(value.value)} {_escape_text(value.unit)}"
    if isinstance(value, str):
        return _escape_text(value)
    if isinstance(value, Enum):
        return _enum_token(value)
    raise HumanReportIntegrityError(f"unsupported report value type: {type(value).__name__}")


def _class_text(target_class: str | None) -> str:
    if target_class is None:
        return "não disponível"
    label = _CLASS_LABELS.get(target_class)
    return f"{label} ({_code(target_class)})" if label else _code(target_class)


def _property_text(property_slot: str) -> str:
    label = _PROPERTY_LABELS.get(property_slot)
    return f"{label} ({_code(property_slot)})" if label else _code(property_slot)


def _rule_text(rule_ref) -> str:
    return "não disponível" if rule_ref is None else _code(rule_ref.rule_id)


def _tokens(values) -> str:
    if not values:
        return "nenhum"
    rendered = []
    for value in values:
        if isinstance(value, Enum):
            rendered.append(_enum_token(value))
        elif hasattr(value, "code") and isinstance(value.code, str):
            rendered.append(_code(value.code))
        else:
            raise HumanReportIntegrityError("unexpected token/warning type")
    return ", ".join(rendered)


def _append_empty_or_items(lines: list[str], items, render_item) -> None:
    if not items:
        lines.extend(["Nenhum item.", ""])
        return
    for index, item in enumerate(items, start=1):
        render_item(lines, index, item)
    lines.append("")


def _render_applied(lines: list[str], index: int, item) -> None:
    lines.extend(
        [
            f"{index}. **{_class_text(item.target.target_class)} — {_property_text(item.target.property_slot)}**",
            f"   - Antes: {_value_text(item.observed_before)}",
            f"   - Aplicado: {_value_text(item.desired_applied)}",
            f"   - Localização técnica: {_code(item.target.structural_path)}",
            f"   - Regra: {_rule_text(item.rule_ref)}",
            f"   - Transformação: {_code(item.transform_ref)}",
        ]
    )


def _render_unapplied(lines: list[str], index: int, item) -> None:
    lines.extend(
        [
            f"{index}. **{_class_text(item.target.target_class)} — {_property_text(item.target.property_slot)}**",
            f"   - Observado: {_value_text(item.observed)}",
            f"   - Desejado: {_value_text(item.desired_value)}",
            f"   - Razão registrada: {_code(item.reason)}",
            f"   - Tipo de ocorrência: {_enum_token(item.finding_kind)}",
            f"   - Localização técnica: {_code(item.target.structural_path)}",
            f"   - Regra: {_rule_text(item.rule_ref)}",
        ]
    )


def _render_review(lines: list[str], index: int, item) -> None:
    lines.extend(
        [
            f"{index}. **{_class_text(item.target.target_class)} — {_property_text(item.target.property_slot)}**",
            f"   - Ação requerida: {_enum_token(item.actionability)}",
            f"   - Razão registrada: {_enum_token(item.reason)}",
            f"   - Observado: {_value_text(item.observed)}",
            f"   - Localização técnica: {_code(item.target.structural_path)}",
            f"   - Regra: {_rule_text(item.rule_ref)}",
            f"   - Avisos: {_tokens(item.decision_warnings)}",
        ]
    )


def _render_classification(lines: list[str], index: int, item) -> None:
    lines.extend(
        [
            f"{index}. **Alvo {_code(item.target_type)} — {_class_text(item.target_class)}**",
            f"   - Status: {_enum_token(item.classification_status)}",
            f"   - Story: {_code(item.story_id)}",
            f"   - Localização técnica: {_code(item.structural_path)}",
            f"   - Razões: {_tokens(item.reasons)}",
            f"   - Avisos: {_tokens(item.classification_warnings)}",
        ]
    )


def render_processing_report(report: ProcessingReport) -> RenderedProcessingReport:
    """Render one frozen ProcessingReport into deterministic pt-BR Markdown."""
    if not isinstance(report, ProcessingReport):
        raise HumanReportContractError("report must be ProcessingReport")
    if report.processing_report_version != "0.1":
        raise HumanReportIntegrityError("unsupported ProcessingReport version")

    summary = report.summary
    lines = [
        "# Relatório de processamento",
        "",
        "## Resumo",
        "",
        f"- Status técnico da sessão: {_enum_token(summary.session_status)}",
        f"- Alterações aplicadas: {summary.applied_change_count}",
        f"- Alterações não aplicadas: {summary.unapplied_change_count}",
        f"- Itens para revisão: {summary.review_item_count}",
        f"- Observações de classificação: {summary.classification_item_count}",
        f"- Classificações finais: {summary.final_classification_count}",
        f"- Classificadas: {summary.classified_count}",
        f"- Abstidas: {summary.abstained_count}",
        f"- Não aplicáveis: {summary.not_applicable_count}",
        f"- Avisos de classificação: {summary.classification_warning_count}",
        "",
        "O status técnico `quiescent` indica apenas que não restou automação segura a executar no slice atual; não significa conformidade integral.",
        "",
        "## Alterações aplicadas",
        "",
    ]
    _append_empty_or_items(lines, report.applied_changes, _render_applied)
    lines.extend(["## Alterações não aplicadas", ""])
    _append_empty_or_items(lines, report.unapplied_changes, _render_unapplied)
    lines.extend(["## Itens para revisão", ""])
    _append_empty_or_items(lines, report.review_items, _render_review)
    lines.extend(["## Observações de classificação", ""])
    _append_empty_or_items(lines, report.classification_items, _render_classification)
    lines.extend(
        [
            "## Limitações e interpretação",
            "",
            "- Este relatório é uma apresentação derivada do processamento e não prova conformidade integral com qualquer norma ou perfil.",
            "- Resultados abstidos ou não aplicáveis permanecem fora de uma conclusão normativa.",
            "- O DOCX de revisão usa destaque visual apenas para indicar que existe informação correspondente no relatório; a cor não representa prioridade.",
            "- No slice atual, a correção automática de tamanho de fonte não altera `w:szCs`; isso é uma limitação geral e não um diagnóstico específico deste arquivo.",
        ]
    )

    text = "\n".join(lines).rstrip("\n") + "\n"
    content = text.encode("utf-8", errors="strict")
    return RenderedProcessingReport(
        human_report_version=HUMAN_REPORT_VERSION,
        processing_report_ref=processing_report_ref(report),
        media_type=HUMAN_REPORT_MEDIA_TYPE,
        content_bytes=content,
        content_sha256=hashlib.sha256(content).hexdigest(),
    )
