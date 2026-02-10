# Copyright (c) 2026, 4C Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

total_sales_amount = total_sales_vat_amount = 0
total_purchase_amount = total_purchase_vat_amount = 0

def execute(filters=None):
	columns = get_columns()
	data, emirates, amounts_by_emirate = get_data(filters)
	return columns, data


def get_columns():
	"""Creates a list of dictionaries that are used to generate column headers of the data table."""
	return [
		{"fieldname": "no", "label": _("No"), "fieldtype": "Data", "width": 50},
		{"fieldname": "legend", "label": _("Legend"), "fieldtype": "Data", "width": 300},
		{
			"fieldname": "amount",
			"label": _("Amount (AED)"),
			"fieldtype": "Currency",
			"width": 125,
		},
		{
			"fieldname": "vat_amount",
			"label": _("VAT Amount (AED)"),
			"fieldtype": "Currency",
			"width": 150,
		},
	]


def get_data(filters=None):
	"""Returns the list of dictionaries. Each dictionary is a row in the datatable and chart data."""
	data = []
	global total_sales_vat_amount, total_purchase_vat_amount

	emirates, amounts_by_emirate = append_vat_on_sales(data, filters)
	append_vat_on_expenses(data, filters)
	append_data(data, "", "", "", "")
	append_data(data, "", _("Net VAT Due"), "", "")
	append_data(data, "12", _("Total Value of due tax for the period"), frappe.format(total_sales_vat_amount, "Currency"), "")
	append_data(data, "13", _("Total Value of recoverable tax for the period"), frappe.format(total_purchase_vat_amount, "Currency"), "")
	append_data(data, "14", _("Net VAT due(or reclaimed) for the period"), frappe.format(total_sales_vat_amount-total_purchase_vat_amount, "Currency"), "")
	return data, emirates, amounts_by_emirate


def append_vat_on_sales(data, filters):
	"""Appends Sales and All Other Outputs."""
	append_data(data, "", _("VAT on Sales and All Other Outputs"), "", "")

	emirates, amounts_by_emirate = standard_rated_expenses_emiratewise(data, filters)

	append_data(
		data,
		"2",
		_("Tax Refunds provided to Tourists under the Tax Refunds for Tourists Scheme"),
		frappe.format((-1) * get_tourist_tax_return_total(filters), "Currency"),
		frappe.format((-1) * get_tourist_tax_return_tax(filters), "Currency"),
	)

	append_data(data, "3", _("Supplies subject to the reverse charge provision"), frappe.format(get_zero_rated_purchases(filters), "Currency"), "-")

	append_data(data, "4", _("Zero Rated"), frappe.format(get_zero_rated_total(filters), "Currency"), "-")

	append_data(data, "5", _("Exempt Supplies"), frappe.format(get_exempt_total(filters), "Currency"), "-")

	append_data(
		data,
		"6",
		_("Goods imported into UAE"),
		frappe.format(get_reverse_charge_recoverable_total(filters), "Currency"),
		frappe.format(get_reverse_charge_recoverable_tax(filters), "Currency"),
	)

	append_data(data, "7", _("Adjustments to goods imported into UAE"), "-", "-")

	global total_sales_amount, total_sales_vat_amount
	total_sales_amount = total_sales_vat_amount = 0
	for row in data:
		total_sales_amount += flt(row.get("amount"))
		total_sales_vat_amount += flt(row.get("vat_amount"))

	append_data(data, "8", _("Totals"), frappe.format(total_sales_amount, "Currency"), frappe.format(total_sales_vat_amount, "Currency"))

	append_data(data, "", "", "", "")

	return emirates, amounts_by_emirate


def standard_rated_expenses_emiratewise(data, filters):
	"""Append emiratewise standard rated expenses and vat."""
	total_emiratewise = get_total_emiratewise(filters)
	emirates = get_emirates()
	amounts_by_emirate = {}
	for emirate, amount, vat in total_emiratewise:
		amounts_by_emirate[emirate] = {
			"legend": emirate,
			"raw_amount": amount,
			"raw_vat_amount": vat,
			"amount": frappe.format(amount, "Currency"),
			"vat_amount": frappe.format(vat, "Currency"),
		}
	amounts_by_emirate = append_emiratewise_expenses(data, emirates, amounts_by_emirate)
	return emirates, amounts_by_emirate


def append_emiratewise_expenses(data, emirates, amounts_by_emirate):
	"""Append emiratewise standard rated expenses and vat."""
	for no, emirate in enumerate(emirates, 97):
		if emirate in amounts_by_emirate:
			amounts_by_emirate[emirate]["no"] = _("1{0}").format(chr(no))
			amounts_by_emirate[emirate]["legend"] = _("Standard rated supplies in {0}").format(emirate)
			data.append(amounts_by_emirate[emirate])
		else:
			append_data(
				data,
				_("1{0}").format(chr(no)),
				_("Standard rated supplies in {0}").format(emirate),
				frappe.format(0, "Currency"),
				frappe.format(0, "Currency"),
			)
	return amounts_by_emirate


def append_vat_on_expenses(data, filters):
	"""Appends Expenses and All Other Inputs."""
	append_data(data, "", _("VAT on Expenses and All Other Inputs"), "", "")
	total_taxable_amount, total_vat = get_vat_debit_totals(filters)
	expense_claim_taxable_amount, expense_claim_vat = get_expense_claim_vat_totals(filters)
	standard_rated_purchase_amount = get_standard_rated_expenses_total(filters)
	standard_rated_purchase_tax_amount = get_standard_rated_expenses_tax(filters)
	append_data(
		data,
		"9",
		_("Standard Rated Expenses"),
		frappe.format(standard_rated_purchase_amount + total_taxable_amount + expense_claim_taxable_amount, "Currency"),
		frappe.format(standard_rated_purchase_tax_amount + total_vat + expense_claim_vat, "Currency"),
	)
	append_data(
		data,
		"10",
		_("Supplies subject to the reverse charge provision"),
		frappe.format(get_reverse_charge_recoverable_total(filters), "Currency"),
		frappe.format(get_reverse_charge_recoverable_tax(filters), "Currency"),
	)

	global total_purchase_amount, total_purchase_vat_amount
	total_purchase_amount = total_purchase_vat_amount = 0
	total_purchase_amount = standard_rated_purchase_amount + total_taxable_amount + expense_claim_taxable_amount + get_reverse_charge_recoverable_total(filters)
	total_purchase_vat_amount = standard_rated_purchase_tax_amount + total_vat + expense_claim_vat + get_reverse_charge_recoverable_tax(filters)
	append_data(data, "11", _("Totals"), frappe.format(total_purchase_amount, "Currency"), frappe.format(total_purchase_vat_amount, "Currency"))


def append_data(data, no, legend, amount, vat_amount):
	"""Returns data with appended value."""
	data.append({"no": no, "legend": legend, "amount": amount, "vat_amount": vat_amount})


def get_total_emiratewise(filters):
	"""Returns Emiratewise Amount and Taxes."""
	conditions = get_conditions(filters)
	try:
		sales_data = frappe.db.sql(
			f"""
			select
				s.vat_emirate as emirate, sum(i.base_net_amount) as total,
				sum(
					CASE
						WHEN s.currency = 'AED' THEN i.tax_amount
						ELSE (i.base_net_amount * (i.tax_rate / 100))
					END
				)
			from
				`tabSales Invoice Item` i inner join `tabSales Invoice` s
			on
				i.parent = s.name
			where
				s.docstatus = 1 and  s.is_opening = "No" and
				i.is_exempt != 1 and i.is_zero_rated != 1 and i.tax_amount != 0
				{conditions}
			group by
				s.vat_emirate;
			""",
			filters,
		)
		frappe.log_error(title="Emiratewise Sales Data", message=f"{sales_data}")

		return sales_data
	except (IndexError, TypeError):
		return []


def get_emirates():
	"""Returns a List of emirates in the order that they are to be displayed."""
	return ["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"]


def get_filters(filters):
	"""The conditions to be used to filter data to calculate the total sale."""
	query_filters = []
	if filters.get("company"):
		query_filters.append(["company", "=", filters["company"]])
	if filters.get("from_date"):
		query_filters.append(["posting_date", ">=", filters["from_date"]])
	if filters.get("to_date"):
		query_filters.append(["posting_date", "<=", filters["to_date"]])
	return query_filters


def get_reverse_charge_total(filters):
	"""Returns the sum of the total of each Purchase invoice made."""
	query_filters = get_filters(filters)
	query_filters.append(["reverse_charge", "=", "Y"])
	query_filters.append(["docstatus", "=", 1])
	try:
		return (
			frappe.db.get_all(
				"Purchase Invoice", filters=query_filters, fields=["sum(base_net_total)"], as_list=True, limit=1
			)[0][0]
			or 0
		)
	except (IndexError, TypeError):
		return 0


def get_reverse_charge_tax(filters):
	"""Returns the sum of the tax of each Purchase invoice made."""
	conditions = get_conditions_join(filters)
	return (
		frappe.db.sql(
			f"""
		select sum(debit)  from
			`tabPurchase Invoice` p inner join `tabGL Entry` gl
		on
			gl.voucher_no =  p.name
		where
			p.reverse_charge = "Y"
			and p.docstatus = 1
			and gl.docstatus = 1
			and account in (select account from `tabUAE VAT Account` where  parent=%(company)s)
			{conditions} ;
		""",
			filters,
		)[0][0]
		or 0
	)


def get_reverse_charge_recoverable_total(filters):
	"""Returns the sum of the total of each Purchase invoice made with recoverable reverse charge."""
	condition = get_conditions_join(filters)
	return (
		frappe.db.sql(
			f"""
			SELECT
				SUM(base_net_total)
			FROM
				`tabPurchase Invoice` p
			WHERE
				p.reverse_charge = "Y"
				AND p.docstatus = 1
				AND p.recoverable_reverse_charge > 0
				{condition};
			""",
			filters,
		)[0][0]
		or 0
	)


def get_reverse_charge_recoverable_tax(filters):
	"""Returns the sum of the tax of each Purchase invoice made."""
	conditions = get_conditions_join(filters)
	return (
        frappe.db.sql(
            f"""
            SELECT 
				SUM((base_net_total * p.recoverable_reverse_charge / 100) * 0.05)
            FROM 
                `tabPurchase Invoice` p
            WHERE 
                p.reverse_charge = "Y"
                AND p.docstatus = 1
                AND p.recoverable_reverse_charge > 0
                {conditions};
            """,
            filters,
        )[0][0]
        or 0
    )


def get_conditions_join(filters):
	"""The conditions to be used to filter data to calculate the total vat."""
	conditions = ""
	for opts in (
		("company", " and p.company=%(company)s"),
		("from_date", " and p.posting_date>=%(from_date)s"),
		("to_date", " and p.posting_date<=%(to_date)s"),
	):
		if filters.get(opts[0]):
			conditions += opts[1]
	return conditions


def get_standard_rated_expenses_total(filters):
	"""Returns the sum of the total of each Purchase invoice made with recoverable reverse charge."""
	query_filters = get_filters(filters)
	query_filters.append(["recoverable_standard_rated_expenses", "!=", 0])
	query_filters.append(["docstatus", "=", 1])
	try:
		return (
			frappe.db.get_all(
				"Purchase Invoice", filters=query_filters, fields=["sum(base_net_total)"], as_list=True, limit=1
			)[0][0]
			or 0
		)
	except (IndexError, TypeError):
		return 0


def get_standard_rated_expenses_tax(filters):
	"""Returns the sum of the tax of each Purchase invoice made."""
	query_filters = get_filters(filters)
	query_filters.append(["recoverable_standard_rated_expenses", "!=", 0])
	query_filters.append(["docstatus", "=", 1])
	try:
		return (
			frappe.db.get_all(
				"Purchase Invoice",
				filters=query_filters,
				fields=["sum(recoverable_standard_rated_expenses)"],
				as_list=True,
				limit=1,
			)[0][0]
			or 0
		)
	except (IndexError, TypeError):
		return 0


def get_tourist_tax_return_total(filters):
	"""Returns the sum of the total of each Sales invoice with non zero tourist_tax_return."""
	query_filters = get_filters(filters)
	query_filters.append(["tourist_tax_return", ">", 0])
	query_filters.append(["docstatus", "=", 1])
	try:
		return (
			frappe.db.get_all(
				"Sales Invoice", filters=query_filters, fields=["sum(base_net_total)"], as_list=True, limit=1
			)[0][0]
			or 0
		)
	except (IndexError, TypeError):
		return 0
	

def get_zero_rated_purchases(filters):
	"""Returns the sum of the total of each Purchase invoice made which is zero rated."""
	condition = get_conditions_join(filters)
	return (
		frappe.db.sql(
			f"""
			SELECT
				SUM(base_net_total)
			FROM
				`tabPurchase Invoice` p
			WHERE
				p.reverse_charge = "N"
				AND p.docstatus = 1
				AND p.recoverable_standard_rated_expenses = 0
				{condition};
			""",
			filters,
		)[0][0]
		or 0
	)


def get_tourist_tax_return_tax(filters):
	"""Returns the sum of the tax of each Sales invoice with non zero tourist_tax_return."""
	query_filters = get_filters(filters)
	query_filters.append(["tourist_tax_return", ">", 0])
	query_filters.append(["docstatus", "=", 1])
	try:
		return (
			frappe.db.get_all(
				"Sales Invoice",
				filters=query_filters,
				fields=["sum(tourist_tax_return)"],
				as_list=True,
				limit=1,
			)[0][0]
			or 0
		)
	except (IndexError, TypeError):
		return 0


def get_zero_rated_total(filters):
	"""Returns the sum of each Sales Invoice Item Amount which is zero rated."""
	conditions = get_conditions(filters)
	try:
		return (
			frappe.db.sql(
				f"""
			select
				sum(i.base_net_amount) as total
			from
				`tabSales Invoice Item` i inner join `tabSales Invoice` s
			on
				i.parent = s.name
			where
				s.docstatus = 1 and
				s.is_opening = "No" and
				(i.is_zero_rated = 1 or i.tax_amount = 0) and i.is_exempt != 1 and
				s.taxes_and_charges NOT LIKE "%%UAE VAT 5%%"
				{conditions} ;
			""",
				filters,
			)[0][0]
			or 0
		)
	except (IndexError, TypeError):
		return 0


def get_exempt_total(filters):
	"""Returns the sum of each Sales Invoice Item Amount which is Vat Exempt."""
	conditions = get_conditions(filters)
	try:
		return (
			frappe.db.sql(
				f"""
			select
				sum(i.base_net_amount) as total
			from
				`tabSales Invoice Item` i inner join `tabSales Invoice` s
			on
				i.parent = s.name
			where
				s.docstatus = 1 and
				s.is_opening = "No" and
				i.is_exempt = 1 and  i.is_zero_rated != 1
				{conditions} ;
			""",
				filters,
			)[0][0]
			or 0
		)
	except (IndexError, TypeError):
		return 0


def get_conditions(filters):
	"""The conditions to be used to filter data to calculate the total sale."""
	conditions = ""
	for opts in (
		("company", " and company=%(company)s"),
		("from_date", " and posting_date>=%(from_date)s"),
		("to_date", " and posting_date<=%(to_date)s"),
	):
		if filters.get(opts[0]):
			conditions += opts[1]
	return conditions


def get_vat_debit_totals(filters):
	"""
	Fetch the total VAT debit and the total taxable amount for which this VAT (5%) debit has occurred.
	"""
	journal_entries = frappe.get_all(
		"Journal Entry",
		filters={
			"docstatus": 1,
			"posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
		},
		fields=["name"]
	)

	if not journal_entries:
		return 0, 0

	journal_entry_names = [je["name"] for je in journal_entries]
	
	vat_account = get_vat_account()

	if not vat_account:
		return 0, 0

	vat_entries = frappe.get_all(
		"Journal Entry Account",
		filters={
			"parent": ["in", journal_entry_names],
			"account": vat_account,  # Match VAT accounts
		},
		fields=["parent", "debit", "credit"]
	)

	if not vat_entries:
		return 0, 0

	journal_entry_vat_map = {}
	for entry in vat_entries:
		je_name = entry["parent"]
		if je_name not in journal_entry_vat_map:
			journal_entry_vat_map[je_name] = {"net_vat": 0.0, "taxable_amount": 0.0}
		net_vat = (entry.get("debit") or 0) - (entry.get("credit") or 0)
		journal_entry_vat_map[je_name]["net_vat"] += net_vat
		journal_entry_vat_map[je_name]["taxable_amount"] += (net_vat * 20)

	total_vat = sum(v["net_vat"] for v in journal_entry_vat_map.values())
	total_taxable_amount = sum(v["taxable_amount"] for v in journal_entry_vat_map.values())

	return total_taxable_amount, total_vat


def get_expense_claim_vat_totals(filters):
	"""
	Fetch VAT and taxable amount from Expense Claim GL Entries
	where account matches VAT account and GL Entry is submitted.
	"""
	vat_accounts = get_vat_account()

	if not vat_accounts:
		return 0, 0

	gl_entries = frappe.get_all(
		"GL Entry",
		filters={
			"docstatus": 1,
			"voucher_type": "Expense Claim",
			"posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
			"account": vat_accounts,
		},
		fields=["debit", "credit"],
	)

	if not gl_entries:
		return 0, 0

	total_net_vat = 0.0
	total_taxable_amount = 0.0

	for entry in gl_entries:
		net_vat = (entry.get("debit") or 0) - (entry.get("credit") or 0)
		total_net_vat += net_vat
		total_taxable_amount += net_vat * 20  # 5% VAT

	return total_taxable_amount, total_net_vat


def get_vat_account():
	"""Return VAT accounts from Assets if exists, else from Liabilities."""
	asset_vat_accounts = frappe.db.get_value(
		"Account",
		{
			"root_type": "Asset",
			"name": ["like", "%VAT 5%"],
			"is_group": 0,
		},
		pluck="name",
	)

	if asset_vat_accounts:
		return asset_vat_accounts

	# fallback to Liability VAT accounts
	return frappe.db.get_value(
		"Account",
		{
			"root_type": "Liability",
			"name": ["like", "%VAT 5%"],
			"is_group": 0,
		},
		pluck="name",
	)

