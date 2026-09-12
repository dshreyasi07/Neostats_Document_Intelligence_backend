import json
import os
from math import isclose


def validate_financials(document_type, extracted_data):
    if os.getenv("GEMINI_API_KEY"):
        try:
            gemini_result = _validate_with_gemini(extracted_data)
            deterministic = _validate_deterministic(document_type, extracted_data)
            return _merge_validation_results(gemini_result, deterministic)
        except Exception:
            pass
    return _validate_deterministic(document_type, extracted_data)


def _validate_deterministic(document_type, extracted_data):
    values = {key: item.get("value") if isinstance(item, dict) else item for key, item in extracted_data.items()}
    checks = []
    if document_type == "invoice":
        checks.extend(_invoice_checks(values))
    elif document_type == "balance_sheet":
        checks.extend(_balance_sheet_checks(values))
    else:
        specs = {
            "profit_and_loss": ("net_profit_check", "total_income - total_expenditure", ("total_income", "total_expenditure", "consolidated_net_profit")),
            "cash_flow_statement": ("net_cash_flow_check", "operating_cash_flow + investing_cash_flow + financing_cash_flow + fx_adjustment", ("operating_cash_flow", "investing_cash_flow", "financing_cash_flow", "fx_adjustment", "net_increase_in_cash")),
        }
        name, formula, fields = specs[document_type]
        check = _check(name, formula, values, *fields)
        if check:
            checks.append(check)
    return _result(checks)


def _invoice_checks(values):
    checks = []
    line_items = _list_value(values, "line_items", "items", "invoice_items")
    for index, item in enumerate(line_items or [], start=1):
        quantity = _item_number(item, "quantity", "qty")
        unit_price = _item_number(item, "unit_price", "unitPrice", "price")
        reported = _item_number(item, "amount", "line_total", "line_amount", "total")
        if quantity is not None and unit_price is not None and reported is not None:
            calculated = quantity * unit_price
            checks.append(_comparison_check(f"invoice_line_item_{index}_check", "quantity * unit_price", {"quantity": quantity, "unit_price": unit_price}, calculated, reported))
    total_check = _check("invoice_total_check", "subtotal + tax_amount - discount", values, "subtotal", "tax_amount", "discount", "total_amount")
    if total_check:
        checks.append(total_check)
    elif line_items:
        subtotal = _number(values.get("subtotal"))
        total = _number(values.get("total_amount"))
        if subtotal is not None and total is not None:
            line_total = sum((_item_number(item, "amount", "line_total", "line_amount", "total") or 0) for item in line_items)
            checks.append(_comparison_check("invoice_line_items_subtotal_check", "sum(line item amounts)", {}, line_total, subtotal))
    return checks


def _balance_sheet_checks(values):
    checks = []
    assets = _first_number(values, "total_assets", "assets_total", "total_asset")
    capital_liabilities = _first_number(values, "total_capital_and_liabilities", "capital_and_liabilities_total", "total_liabilities_and_equity", "liabilities_and_equity_total")
    if assets is not None and capital_liabilities is not None:
        checks.append(_comparison_check("balance_sheet_sides_check", "total assets = total capital and liabilities", {"total_assets": assets}, assets, capital_liabilities))
    asset_items = _list_value(values, "assets", "asset_items")
    liability_items = _list_value(values, "capital_and_liabilities", "liabilities_and_equity", "capital_liabilities", "liability_items")
    if asset_items and assets is not None:
        amounts = [_item_number(item, "amount", "value", "total") for item in asset_items]
        if all(amount is not None for amount in amounts):
            checks.append(_comparison_check("balance_sheet_assets_components_check", "sum(asset components) = total assets", {}, sum(amounts), assets))
    if liability_items and capital_liabilities is not None:
        amounts = [_item_number(item, "amount", "value", "total") for item in liability_items]
        if all(amount is not None for amount in amounts):
            checks.append(_comparison_check("balance_sheet_capital_liabilities_components_check", "sum(capital and liability components) = total capital and liabilities", {}, sum(amounts), capital_liabilities))
    return checks


def _result(checks):
    return {"checks": checks, "overall_status": "PASS" if checks and all(check["status"] == "PASS" for check in checks) else ("NOT_APPLICABLE" if not checks else "FAIL"), "issues": [check["name"] for check in checks if check["status"] == "FAIL"]}


def _merge_validation_results(primary, deterministic):
    checks = primary.get("checks", []) + deterministic.get("checks", [])
    return _result(checks) if checks else primary


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _first_number(values, *keys):
    for key in keys:
        number = _number(values.get(key))
        if number is not None:
            return number
    return None


def _list_value(values, *keys):
    for key in keys:
        value = values.get(key)
        if isinstance(value, list):
            return value
    return []


def _item_number(item, *keys):
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        number = _number(value)
        if number is not None:
            return number
    return None


def _comparison_check(name, formula, operands, calculated, reported):
    variance = round(calculated - reported, 2)
    return {"name": name, "formula": formula, "operands": operands, "calculated_value": calculated, "reported_value": reported, "variance": variance, "status": "PASS" if isclose(calculated, reported, abs_tol=0.05) else "FAIL"}


def _validate_with_gemini(extracted_data):
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=json.dumps(extracted_data, default=str),
        config={"response_mime_type": "application/json", "system_instruction": """You are a financial validation engine. Validate only the supplied extracted data. Do not perform document extraction and do not invent or repair values.

Recalculate every possible financial relationship using the actual values present:
- invoice: each quantity * unit_price must equal its line amount; sum of line amounts must reconcile with subtotal; subtotal + tax - discount must equal total amount. Handle tax-included totals explicitly. Check for the values along with original and the final value after considering all discounts and taxes.
- balance_sheet: total assets must equal total capital and liabilities; sum asset components must equal total assets; sum capital/liability components must equal total capital and liabilities.
- profit_and_loss: income, expenditure, and net profit relationships must reconcile.
- cash_flow_statement: operating + investing + financing + FX adjustment must equal net cash change; opening cash plus net change must equal closing cash.

Use parentheses as negative numbers. Use a tolerance of 0.05 for currency rounding. Do not assume missing fields: return NOT_APPLICABLE for a relationship when its required values are absent. Return FAIL whenever an available calculation does not reconcile. Return only JSON in this shape: {"checks":[{"name":"...","formula":"...","operands":{},"calculated_value":null,"reported_value":null,"variance":null,"status":"PASS|FAIL|NOT_APPLICABLE"}],"overall_status":"PASS|FAIL|NOT_APPLICABLE","issues":[]}.
"""},
    )
    result = json.loads(response.text)
    if not isinstance(result.get("checks"), list) or result.get("overall_status") not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
        raise ValueError("Gemini returned an invalid invoice validation response")
    check_statuses = {check.get("status") for check in result["checks"] if isinstance(check, dict)}
    if "FAIL" in check_statuses:
        result["overall_status"] = "FAIL"
    elif not check_statuses or check_statuses == {"NOT_APPLICABLE"}:
        result["overall_status"] = "NOT_APPLICABLE"
    return result


def _check(name, formula, values, *fields):
    if any(not isinstance(values.get(field), (int, float)) for field in fields):
        return None
    operands = {field: values[field] for field in fields[:-1]}
    reported = values[fields[-1]]
    calculated = sum(operands.values())
    variance = round(calculated - reported, 2)
    return {"name": name, "formula": formula, "operands": operands, "calculated_value": calculated, "reported_value": reported, "variance": variance, "status": "PASS" if isclose(calculated, reported, abs_tol=0.05) else "FAIL"}
