import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.seed import COMMERCIAL, OFFICE

pytestmark = pytest.mark.e2e
TIMEOUT = 60_000


def _enter(page: Page, url: str, category: str, value: str | None = None):
    page.goto(url)
    expect(page.get_by_text("¿Cómo quieres acceder?")).to_be_visible(timeout=TIMEOUT)
    page.get_by_role("combobox").first.click()
    page.get_by_role("option", name=category, exact=True).click()
    if value is not None:
        page.get_by_role("combobox").nth(1).click()
        page.get_by_role("option", name=value, exact=True).click()
    page.locator('[class*="st-key-vision_access_enter"] button').click()


def _change_access(page: Page):
    page.get_by_role("button", name=re.compile("Cambiar acceso")).click()
    expect(page.get_by_text("¿Cómo quieres acceder?")).to_be_visible(timeout=TIMEOUT)


def test_landing_offers_only_safe_options_before_first_load(page: Page, app_url):
    page.goto(app_url)
    expect(page.get_by_text("¿Cómo quieres acceder?")).to_be_visible(timeout=TIMEOUT)
    page.get_by_role("combobox").first.click()
    options = page.get_by_role("option").all_inner_texts()
    assert options == ["Comercial", "Delegación", "O2C"]


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
