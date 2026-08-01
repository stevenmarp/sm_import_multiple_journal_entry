{
    "name": "Import Multiple Journal Entries from Excel/CSV",
    "version": "1.0.0",
    "category": "Accounting",
    "summary": "Bulk import many journal entries and their lines from one Excel or CSV file",
    "description": """
Import Multiple Journal Entries from Excel/CSV
==============================================

Import several journal entries at once from a single Excel or CSV file. Rows sharing the same reference are grouped into one balanced journal entry, and entries can be posted right away.
    """,
    "author": "Steven Marp",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Steven Marp",
    "license": "OPL-1",
    "depends": ["account"],
    "data": ["security/ir.model.access.csv", "wizard/import_multiple_journal_entry_wizard_views.xml"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "images": ["static/description/banner.gif", "static/description/icon.png"],
    "price": 10.00,
    "currency": "USD",
}
