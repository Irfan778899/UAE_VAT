# Copyright (c) 2026, 4C Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from collections import defaultdict

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname": "posting_date",
			"label": _("Date"),
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "voucher_type",
			"label": _("Voucher Type"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "voucher_no",
			"label": _("Voucher No."),
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 200
		},
		{
			"fieldname": "party_type",
			"label": _("Party Type"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "party",
			"label": _("Party"),
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 300
		},
		{
			"fieldname": "taxable_amount",
			"label": _("Taxable Amount"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "vat_amount",
			"label": _("VAT Amount"),
			"fieldtype": "Currency",
			"width": 120
		}
	]

def get_data(filters):
	data = []
	
	# Get standard rated sales (Row 1a to 1g)
	data.extend(get_standard_rated_sales(filters))

	# Get tourist tax returns (Row 2)
	data.extend(get_tourist_tax_returns(filters))
	
	# Get reverse charge supplies (Row 3)
	data.extend(get_zero_rated_purchases(filters))
	
	# Get zero rated supplies (Row 4)
	data.extend(get_zero_rated_sales(filters))
	
	# Get exempt supplies (Row 5)
	data.extend(get_exempt_sales(filters))
	
	# Get imported goods (Row 6)
	data.extend(get_imported_goods(filters))
	
	# Get standard rated expenses (Row 9)
	data.extend(get_standard_rated_purchases(filters))
	
	# Get reverse charge purchases (Row 10)
	data.extend(get_reverse_charge_purchases(filters))

	data.extend(get_journal_entry_input_vat(filters))

	data.extend(get_expense_claim_input_vat(filters))

	if 'row_no' in filters and filters['row_no']:
		row_no_filter = filters['row_no']
		data = [row for row in data if row['row_no'] == row_no_filter]

	grouped = defaultdict(list)

	# 👇 Group only by row_no
	for row in data:
		key = row["row_no"]
		grouped[key].append(row)

	final = []

	# Natural sort based on row_no
	for row_no in grouped.keys():
		rows = grouped[row_no]

		# Use first legend found for the row (or set default if missing)
		legend = rows[0].get("legend", "Unknown Category")

		# Compute totals
		total_tax = sum(flt(r["taxable_amount"]) for r in rows)
		total_vat = sum(flt(r["vat_amount"]) for r in rows)

		# Add header row with total
		final.append({
			"posting_date": None,
			"voucher_type": row_no,
			"voucher_no": legend,
			"party_type": "TOTAL",
			"party": None,
			"taxable_amount": total_tax,
			"vat_amount": total_vat,
			"is_bold": 1
		})

		# Append all transactions under this row_no
		final.extend(rows)

	return final

def get_standard_rated_sales(filters):
	conditions = get_conditions(filters)
	emirates = ["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"]
	
	sales_data = []
	for idx, emirate in enumerate(emirates, 97):  # ASCII 'a' is 97
		row_no = f"1{chr(idx)}"
		emirate_data = frappe.db.sql("""
			SELECT 
				s.posting_date,
				'Sales Invoice' as voucher_type,
				s.name as voucher_no,
				'Customer' as party_type,
				s.customer as party,
				SUM(i.base_net_amount) as taxable_amount,
				SUM(
					CASE
						WHEN s.currency = 'AED' THEN i.tax_amount
						ELSE (i.base_net_amount * (i.tax_rate / 100))
					END
				) as vat_amount,
				CONCAT('Standard rated supplies in ', s.vat_emirate) as legend,
				%(row_no)s as row_no
			FROM 
				`tabSales Invoice Item` i 
				INNER JOIN `tabSales Invoice` s ON i.parent = s.name
			WHERE 
				s.docstatus = 1 
				AND s.is_opening = 'No'
				AND i.is_exempt != 1 
				AND i.is_zero_rated != 1 
				AND i.tax_amount != 0
				AND s.vat_emirate = %(emirate)s
				{conditions}
			GROUP BY s.name
		""".format(conditions=conditions), {**filters, "emirate": emirate, "row_no": row_no}, as_dict=1)
		sales_data.extend(emirate_data)
	return sales_data

def get_tourist_tax_returns(filters):
	conditions = get_conditions(filters)
	
	return frappe.db.sql("""
		SELECT 
			posting_date,
			'Sales Invoice' as voucher_type,
			name as voucher_no,
			'Customer' as party_type,
			customer as party,
			base_net_total as taxable_amount,
			tourist_tax_return as vat_amount,
			'Tax Refunds provided to Tourists under the Tax Refunds for Tourists Scheme' as legend,
			'2' as row_no
		FROM 
			`tabSales Invoice`
		WHERE 
			docstatus = 1
			AND tourist_tax_return > 0
			{conditions}
	""".format(conditions=conditions), filters, as_dict=1)


def get_zero_rated_purchases(filters):
	"""Returns the sum of the total of each Purchase invoice made which is zero rated."""
	conditions = get_conditions(filters)
	return (
		frappe.db.sql("""
			SELECT
				posting_date,
				'Purchase Invoice' as voucher_type,
				name as voucher_no,
				'Supplier' as party_type,
				supplier as party,
				base_net_total as taxable_amount,
				0 as vat_amount,
				'Supplies subject to the reverse charge provision' as legend,
				'3' as row_no
			FROM
				`tabPurchase Invoice`
			WHERE
				reverse_charge = "N"
				AND docstatus = 1
				AND recoverable_standard_rated_expenses = 0
				{conditions};
		""".format(conditions=conditions), filters, as_dict=1)
	)

def get_zero_rated_sales(filters):
	conditions = get_conditions(filters)
	
	return frappe.db.sql("""
		SELECT 
			s.posting_date,
			'Sales Invoice' as voucher_type,
			s.name as voucher_no,
			'Customer' as party_type,
			s.customer as party,
			SUM(i.base_net_amount) as taxable_amount,
			0 as vat_amount,
			'Zero Rated' as legend,
			'4' as row_no
		FROM 
			`tabSales Invoice Item` i 
			INNER JOIN `tabSales Invoice` s ON i.parent = s.name
		WHERE 
			s.docstatus = 1
			AND s.is_opening = 'No'
			AND s.taxes_and_charges NOT LIKE "%%UAE VAT 5%%"
			AND (i.is_zero_rated = 1 OR i.tax_amount = 0)
			AND i.is_exempt != 1
			{conditions}
		GROUP BY s.name
	""".format(conditions=conditions), filters, as_dict=1)

def get_exempt_sales(filters):
	conditions = get_conditions(filters)
	
	return frappe.db.sql("""
		SELECT 
			s.posting_date,
			'Sales Invoice' as voucher_type,
			s.name as voucher_no,
			'Customer' as party_type,
			s.customer as party,
			SUM(i.base_net_amount) as taxable_amount,
			0 as vat_amount,
			'Exempt Supplies' as legend,
			'5' as row_no
		FROM 
			`tabSales Invoice Item` i 
			INNER JOIN `tabSales Invoice` s ON i.parent = s.name
		WHERE 
			s.docstatus = 1 
			AND s.is_opening = 'No'
			AND i.is_exempt = 1
			AND i.is_zero_rated != 1
			{conditions}
		GROUP BY s.name
	""".format(conditions=conditions), filters, as_dict=1)

def get_imported_goods(filters):
	conditions = get_conditions(filters)
	return frappe.db.sql("""
		SELECT 
			posting_date,
			'Purchase Invoice' as voucher_type,
			name as voucher_no,
			'Supplier' as party_type,
			supplier as party,
			base_net_total AS taxable_amount,
			(
				base_net_total * recoverable_reverse_charge / 100
			) * 0.05 as vat_amount,
			'Goods imported into UAE' as legend,
			'6' as row_no
		FROM 
			`tabPurchase Invoice`
		WHERE 
			docstatus = 1
			AND reverse_charge = 'Y'
			AND recoverable_reverse_charge > 0
			{conditions}
	""".format(conditions=conditions), filters, as_dict=1)


def get_standard_rated_purchases(filters):
	conditions = get_conditions(filters)

	return frappe.db.sql("""
		SELECT 
			posting_date,
			'Purchase Invoice' as voucher_type,
			name as voucher_no,
			'Supplier' as party_type,
			supplier as party,
			base_net_total as taxable_amount,
			recoverable_standard_rated_expenses as vat_amount,
			'Standard Rated Expenses' as legend,
			'9' as row_no
		FROM 
			`tabPurchase Invoice`
		WHERE 
			docstatus = 1
			AND recoverable_standard_rated_expenses != 0
			{conditions}
	""".format(conditions=conditions), filters, as_dict=1)


def get_reverse_charge_purchases(filters):
	conditions = get_conditions(filters)
	return frappe.db.sql("""
		SELECT 
			posting_date,
			'Purchase Invoice' as voucher_type,
			name as voucher_no,
			'Supplier' as party_type,
			supplier as party,
			base_net_total AS taxable_amount,
			(
				base_net_total * recoverable_reverse_charge / 100
			) * 0.05 as vat_amount,
			'Supplies subject to the reverse charge provision' as legend,
			'10' as row_no
		FROM 
			`tabPurchase Invoice`
		WHERE 
			docstatus = 1
			AND reverse_charge = 'Y'
			AND recoverable_reverse_charge > 0
			{conditions}
	""".format(conditions=conditions), filters, as_dict=1)


def get_conditions(filters):
	conditions = ""
	for opts in (
		("company", " and company=%(company)s"),
		("from_date", " and posting_date>=%(from_date)s"),
		("to_date", " and posting_date<=%(to_date)s"),
	):
		if filters.get(opts[0]):
			conditions += opts[1]
	return conditions


def get_journal_entry_input_vat(filters):
	"""Row 9 Add Journal Entries with Input VAT as standard-rated expenses."""
	conditions = get_conditions(filters)
	vat_account = get_vat_account()
	if not vat_account:
		return []

	input_vat_entries = frappe.db.sql(f"""
		SELECT
			je.posting_date,
			je.name AS journal_entry,
			jea.debit,
			jea.credit
		FROM
			`tabJournal Entry` je
			INNER JOIN `tabJournal Entry Account` jea ON je.name = jea.parent
		WHERE
			je.docstatus = 1
			AND jea.account = %(vat_account)s
			{conditions}
	""", {**filters, "vat_account": vat_account}, as_dict=1)

	if not input_vat_entries:
		return []

	entries = []

	for entry in input_vat_entries:
		party_info = frappe.db.get_all(
			"Journal Entry Account",
			filters={
				"parent": entry.journal_entry,
				"party": ["!=", ""]
			},
			fields=["party", "party_type"],
			limit=1
		)

		party_type = party_info[0]["party_type"] if party_info else None
		party = party_info[0]["party"] if party_info else None

		net_vat = flt(entry.debit) - flt(entry.credit)
		taxable_amount = flt(net_vat * 20)

		entries.append({
			"posting_date": entry.posting_date,
			"voucher_type": "Journal Entry",
			"voucher_no": entry.journal_entry,
			"party_type": party_type,
			"party": party,
			"taxable_amount": taxable_amount,
			"vat_amount": flt(net_vat),
			"legend": "Other Standard Rated Expenses (from Journal Entry)",
			"row_no": "9"
		})

	return entries

def get_expense_claim_input_vat(filters):
	"""Row 9 Add Expense Claims with Input VAT as standard-rated expenses."""
	vat_accounts = get_vat_account()

	if not vat_accounts:
		return []

	gl_entries = frappe.get_all(
		"GL Entry",
		filters={
			"docstatus": 1,
			"voucher_type": "Expense Claim",
			"posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
			"account": vat_accounts,
		},
		fields=["debit", "credit", "voucher_no", "posting_date", "against"],
	)

	if not gl_entries:
		return []
	
	entries = []

	for entry in gl_entries:
		net_vat = flt(entry.get("debit") or 0) - flt(entry.get("credit") or 0)
		if not net_vat:
			continue
		entries.append({
			"posting_date": entry.get("posting_date"),
			"voucher_type": "Expense Claim",
			"voucher_no": entry.get("voucher_no"),
			"party_type": "Employee",
			"party": entry.get("against"),
			"taxable_amount": flt(net_vat * 20, 2),  # 5% VAT
			"vat_amount": net_vat,
			"legend": "Other Standard Rated Expenses (from Expense Claim)",
			"row_no": "9"
		})

	return entries
	

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
