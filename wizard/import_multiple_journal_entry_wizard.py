import base64
import csv
import io
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")


def read_rows(datas, filename):
    """Return a list of row lists from a CSV or XLSX file (base64 datas)."""
    content = base64.b64decode(datas or b"")
    rows = []
    if filename and filename.lower().endswith(".csv"):
        text = content.decode("utf-8-sig", errors="ignore")
        for r in csv.reader(io.StringIO(text)):
            if any((c or "").strip() for c in r):
                rows.append([(c or "").strip() for c in r])
    else:
        try:
            import openpyxl
        except ImportError:
            raise UserError(_("The openpyxl python library is required to import Excel files. Use a CSV file instead."))
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            if row and any(c is not None and str(c).strip() for c in row):
                rows.append(["" if c is None else c for c in row])
    return rows


def cell(row, i):
    """Value of column i as a stripped string, empty when missing."""
    if len(row) <= i:
        return ""
    value = row[i]
    return "" if value is None else str(value).strip()


def to_date(value, line_no):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = "" if value is None else str(value).strip()
    if not text:
        return False
    if " " in text:
        text = text.split(" ")[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise UserError(_("Row %s: '%s' is not a valid date.") % (line_no, value))


def to_float(value):
    text = "" if value is None else str(value).strip()
    if not text:
        return 0.0
    return float(text.replace(",", ""))


class ImportJournalEntryWizard(models.TransientModel):
    _name = "sm.import.multiple.journal.entry.wizard"
    _description = "Import Multiple Journal Entries"

    journal_id = fields.Many2one(
        "account.journal", string="Journal", required=True,
        domain="[('type', 'in', ['general', 'bank', 'cash'])]")
    import_file = fields.Binary(string="File", required=True)
    file_name = fields.Char(string="File Name")
    has_header = fields.Boolean(string="File Has Header Row", default=True)
    post_entries = fields.Boolean(string="Post Entries")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "journal_id" in fields_list and not res.get("journal_id"):
            journal = self.env["account.journal"].search(
                [("type", "=", "general"), ("company_id", "=", self.env.company.id)], limit=1)
            res["journal_id"] = journal.id
        return res

    def _find_account(self, code, line_no):
        account = self.env["account.account"].search([("code", "=", code)], limit=1)
        if not account:
            raise UserError(_("Row %s: no account found with code '%s'.") % (line_no, code))
        return account

    def _find_partner(self, name):
        if not name:
            return False
        partner = self.env["res.partner"].search([("name", "=", name)], limit=1)
        return partner.id or False

    def action_import(self):
        self.ensure_one()
        rows = read_rows(self.import_file, self.file_name)
        if self.has_header and rows:
            rows = rows[1:]
        if not rows:
            raise UserError(_("The file has no data rows."))

        groups = {}
        order = []
        for line_no, row in enumerate(rows, start=1):
            ref = cell(row, 0)
            if not ref:
                continue
            if ref not in groups:
                groups[ref] = []
                order.append(ref)
            groups[ref].append((line_no, row))

        if not groups:
            raise UserError(_("No row has a reference in the first column."))

        Move = self.env["account.move"]
        moves = Move.browse()
        for ref in order:
            entry_rows = groups[ref]
            line_vals = []
            total_debit = total_credit = 0.0
            entry_date = False
            for line_no, row in entry_rows:
                entry_date = entry_date or to_date(row[1] if len(row) > 1 else "", line_no)
                account = self._find_account(cell(row, 2), line_no)
                debit = to_float(row[5] if len(row) > 5 else "")
                credit = to_float(row[6] if len(row) > 6 else "")
                total_debit += debit
                total_credit += credit
                line_vals.append((0, 0, {
                    "account_id": account.id,
                    "name": cell(row, 3) or ref,
                    "partner_id": self._find_partner(cell(row, 4)),
                    "debit": debit,
                    "credit": credit,
                }))
            if round(total_debit - total_credit, 2):
                raise UserError(_(
                    "Entry '%(ref)s' is not balanced: debit %(debit)s, credit %(credit)s.",
                    ref=ref, debit=total_debit, credit=total_credit))
            vals = {
                "move_type": "entry",
                "journal_id": self.journal_id.id,
                "ref": ref,
                "line_ids": line_vals,
            }
            if entry_date:
                vals["date"] = entry_date
            moves |= Move.create(vals)

        if self.post_entries:
            moves.action_post()

        return {
            "type": "ir.actions.act_window",
            "name": _("Imported Journal Entries"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }
