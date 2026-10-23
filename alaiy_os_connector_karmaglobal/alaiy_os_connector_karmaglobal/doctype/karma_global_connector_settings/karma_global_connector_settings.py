# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class KarmaGlobalConnectorSettings(Document):
    def validate(self):
        if frappe.db.exists("OS Connector Registry", "karmaglobal"):
            frappe.db.set_value("OS Connector Registry", "karmaglobal", "is_enabled", self.is_enabled)
