"""Client for the DENASUS feature.

Scrapes public gov.br pages (Plone CMS) using httpx + BeautifulSoup.
Rate-limited to 1 request per 3 seconds. No auth required.
"""

from __future__ import annotations

import asyncio
import re

import httpx
from bs4 import BeautifulSoup, Tag

from .constants import (
    ATIVIDADES_URL,
    HEADERS,
    PLANOS_URL,
    RATE_LIMIT_DELAY,
    RELATORIOS_URL,
    UFS_BRASIL,
)
from .schemas import AtividadeAuditoria, PlanoAuditoria, RelatorioAnual


async def _fetch_page(url: str) -> BeautifulSoup:
    """Fetch and parse a gov.br page with rate limiting."""
    await asyncio.sleep(RATE_LIMIT_DELAY)
    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=30.0,
        follow_redirects=True,
    ) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")


def _extrair_uf(titulo: str) -> str | None:
    """Extract UF (state code) from audit activity title."""
    match = re.search(r"\b([A-Z]{2})\b", titulo)
    if match and match.group(1) in UFS_BRASIL:
        return match.group(1)
    return None


def _classificar_tipo(titulo: str) -> str:
    """Classify audit activity type from title."""
    titulo_lower = titulo.lower()
    if "auditoria" in titulo_lower:
        return "Auditoria"
    if "verificação" in titulo_lower or "verificacao" in titulo_lower:
        return "Verificação"
    if "monitoramento" in titulo_lower:
        return "Monitoramento"
    if "inspeção" in titulo_lower or "inspecao" in titulo_lower:
        return "Inspeção"
    return "Outro"


def _extrair_ano(texto: str) -> int | None:
    """Extract year from text like 'Relatório 2024'."""
    match = re.search(r"20[12]\d", texto)
    return int(match.group()) if match else None


def _get_link_href(element: Tag) -> str | None:
    """Extract href from a tag that is or contains a link."""
    if element.name == "a":
        href = element.get("href")
        return str(href) if href else None
    link = element.find("a")
    if isinstance(link, Tag):
        href = link.get("href")
        return str(href) if href else None
    return None


async def listar_atividades_auditoria() -> list[AtividadeAuditoria]:
    """Scrape audit activities from the DENASUS public page."""
    soup = await _fetch_page(ATIVIDADES_URL)
    atividades: list[AtividadeAuditoria] = []

    items = soup.select("article, .item-lista, .tileItem, .documentFirstHeading")

    for item in items:
        if not isinstance(item, Tag):
            continue
        titulo_el = item.select_one("h2, h3, .tileHeadline a, a")
        if not titulo_el:
            continue
        titulo = titulo_el.get_text(strip=True)
        if not titulo:
            continue

        data_el = item.select_one("time, .data, .documentByLine")
        resumo_el = item.select_one("p, .tileBody, .description")

        atividades.append(
            AtividadeAuditoria(
                titulo=titulo,
                data=data_el.get_text(strip=True) if data_el else None,
                uf=_extrair_uf(titulo),
                tipo=_classificar_tipo(titulo),
                situacao="Concluída",
                resumo=resumo_el.get_text(strip=True)[:500] if resumo_el else None,
                url_detalhe=_get_link_href(titulo_el),
            )
        )

    return atividades


async def listar_relatorios_anuais() -> list[RelatorioAnual]:
    """Scrape annual activity reports from the DENASUS page."""
    soup = await _fetch_page(RELATORIOS_URL)
    relatorios: list[RelatorioAnual] = []

    items = soup.select("article, .item-lista, .tileItem, li")
    for item in items:
        if not isinstance(item, Tag):
            continue
        link = item.find("a")
        if not isinstance(link, Tag):
            continue
        titulo = link.get_text(strip=True)
        if not titulo:
            continue
        href = str(link.get("href", ""))
        ano = _extrair_ano(titulo)

        relatorios.append(
            RelatorioAnual(
                ano=ano,
                titulo=titulo,
                url_pdf=href if href.endswith(".pdf") else None,
                resumo=None,
            )
        )

    return relatorios


async def listar_planos_auditoria() -> list[PlanoAuditoria]:
    """Scrape annual audit plans from the DENASUS page."""
    soup = await _fetch_page(PLANOS_URL)
    planos: list[PlanoAuditoria] = []

    items = soup.select("article, .item-lista, .tileItem, li")
    for item in items:
        if not isinstance(item, Tag):
            continue
        link = item.find("a")
        if not isinstance(link, Tag):
            continue
        titulo = link.get_text(strip=True)
        if not titulo:
            continue
        href = str(link.get("href", ""))
        ano = _extrair_ano(titulo)

        planos.append(
            PlanoAuditoria(
                ano=ano,
                titulo=titulo,
                url_pdf=href if href.endswith(".pdf") else None,
            )
        )

    return planos
