import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.seed import COMMERCIAL, OFFICE

pytestmark = pytest.mark.e2e
TIMEOUT = 60_000


def _enter(page: Page, url: str, label: str):
    page.goto(url)
    expect(page.get_by_text("¿Quién va a iniciar sesión?")).to_be_visible(timeout=TIMEOUT)
    page.get_by_role("combobox").first.click()
    page.get_by_role("option", name=label, exact=True).click()
    page.locator('[class*="st-key-vision_access_enter"] button').click()


def _logout(page: Page):
    page.get_by_role("button", name=re.compile("Cerrar sesión")).click()
    expect(page.get_by_text("¿Quién va a iniciar sesión?")).to_be_visible(timeout=TIMEOUT)


def test_landing_offers_only_safe_options_before_first_load(page: Page, app_url):
    page.goto(app_url)
    expect(page.get_by_text("¿Quién va a iniciar sesión?")).to_be_visible(timeout=TIMEOUT)
    page.get_by_role("combobox").first.click()
    options = page.get_by_role("option").all_inner_texts()
    assert "O2C" in options and "Administrator" in options


def test_o2c_flow_and_logout(page: Page, app_url):
    _enter(page, app_url, "O2C")
    expect(page.get_by_role("button", name=re.compile("Cerrar sesión"))).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("Datos actualizados a: 26/10/2026").first).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("SYNTHETIC-ORDER-001").first).to_be_attached(timeout=TIMEOUT)
    _logout(page)


def test_commercial_flow_sees_own_scope_and_logout(page: Page, app_url):
    _enter(page, app_url, "O2C")
    expect(page.get_by_role("button", name=re.compile("Cerrar sesión"))).to_be_visible(timeout=TIMEOUT)
    _logout(page)
    _enter(page, app_url, COMMERCIAL)
    expect(page.get_by_text("Commercial Workspace")).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("Cliente seleccionado: Todos los clientes")).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("SYNTHETIC-ORDER-001").first).to_be_attached(timeout=TIMEOUT)
    _logout(page)


def test_manager_flow_scoped_to_delegation(page: Page, app_url):
    _enter(page, app_url, "O2C")
    expect(page.get_by_role("button", name=re.compile("Cerrar sesión"))).to_be_visible(timeout=TIMEOUT)
    _logout(page)
    _enter(page, app_url, f"{OFFICE} Manager")
    expect(page.get_by_role("button", name=re.compile("Cerrar sesión"))).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("Informes").first).to_be_visible(timeout=TIMEOUT)
    _logout(page)


def test_administrator_shows_date_control(page: Page, app_url):
    _enter(page, app_url, "Administrator")
    expect(page.get_by_text("control de fechas").first).to_be_visible(timeout=TIMEOUT)
