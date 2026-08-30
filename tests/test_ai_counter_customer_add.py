from backend.ai_counter_customer_add_ext import MODAL, SCRIPT, STYLE


def test_customer_add_button_uses_global_kiosk_state_binding():
    assert "typeof S==='undefined'||S.stage!=='customer'" in SCRIPT
    assert "!window.S" not in SCRIPT
    assert "data-add-customer-203" in SCRIPT
    assert "➕ Naya Customer Add Karein" in SCRIPT


def test_customer_add_modal_saves_and_selects_customer():
    assert 'id="customerModal"' in MODAL
    assert 'id="newCustomerName"' in MODAL
    assert 'id="newCustomerPhone"' in MODAL
    assert "Save & Select" in MODAL
    assert "/api/ai-counter/customer" in SCRIPT
    assert "S.customer=d.customer;S.stage='items'" in SCRIPT
    assert "ai-customer-add-203" in STYLE
