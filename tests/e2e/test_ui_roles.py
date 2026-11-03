import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.seed import COMMERCIAL, OFFICE

pytestmark = pytest.mark.e2e
TIMEOUT = 60_000


QUESTION = "¿Quién debe acceder a VISION?"


def _enter(page: Page, url: str, category: str, value: str | None = None):
    page.goto(url)
    expect(page.get_by_text(QUESTION).first).to_be_visible(timeout=TIMEOUT)
    if category == "O2C":
        page.get_by_role("button", name="Acceso O2C").click()
        return
    field = page.get_by_placeholder("Escribe un nombre", exact=False)
    field.fill(value)
    field.press("Enter")

def _change_access(page: Page):
    page.get_by_role("button", name=re.compile("Cambiar acceso")).click()
    expect(page.get_by_text(QUESTION).first).to_be_visible(timeout=TIMEOUT)


def test_landing_offers_only_safe_options_before_first_load(page: Page, app_url):
    page.goto(app_url)
    expect(page.get_by_text(QUESTION).first).to_be_visible(timeout=TIMEOUT)
    assert page.get_by_role("combobox").count() == 0
    expect(page.get_by_placeholder("Escribe un nombre", exact=False)).to_have_count(1)
    expect(page.get_by_role("button", name="Acceso O2C")).to_be_visible(timeout=TIMEOUT)


def test_o2c_flow_and_change_access(page: Page, app_url):
    _enter(page, app_url, "O2C")
    expect(page.get_by_role("button", name=re.compile("Cambiar acceso"))).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("Datos actualizados a: 26/10/2026").first).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("SYNTHETIC-ORDER-001").first).to_be_attached(timeout=TIMEOUT)
    _change_access(page)


def test_commercial_flow_and_change_access(page: Page, app_url):
    _enter(page, app_url, "O2C")
    expect(page.get_by_role("button", name=re.compile("Cambiar acceso"))).to_be_visible(timeout=TIMEOUT)
    _change_access(page)
    _enter(page, app_url, "Comercial", COMMERCIAL)
    expect(page.get_by_text("Commercial Workspace")).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("Cliente seleccionado: Todos los clientes")).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("SYNTHETIC-ORDER-001").first).to_be_attached(timeout=TIMEOUT)
    _change_access(page)


def test_manager_flow_scoped_to_delegation(page: Page, app_url):
    _enter(page, app_url, "O2C")
    expect(page.get_by_role("button", name=re.compile("Cambiar acceso"))).to_be_visible(timeout=TIMEOUT)
    _change_access(page)
    _enter(page, app_url, "Delegación", OFFICE)
    expect(page.get_by_role("button", name=re.compile("Cambiar acceso"))).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("Informes").first).to_be_visible(timeout=TIMEOUT)
    _change_access(page)


def test_data_administration_remains_available_from_workspace(page: Page, app_url):
    _enter(page, app_url, "O2C")
    page.get_by_text("Administración / Datos").click()
    expect(page.get_by_text("control de fechas").first).to_be_visible(timeout=TIMEOUT)


def test_o2c_manager_global_view_and_exit(page: Page, app_url):
    _enter(page, app_url, "Ana", "Ana Feliu")
    expect(page.get_by_role("tab", name="Informe global")).to_be_visible(timeout=TIMEOUT)
    page.get_by_role("tab", name="Informe global").click()
    expect(page.locator('[data-testid="stMetricLabel"]').filter(has_text="Máquinas").first).to_be_visible(timeout=TIMEOUT)
    _change_access(page)