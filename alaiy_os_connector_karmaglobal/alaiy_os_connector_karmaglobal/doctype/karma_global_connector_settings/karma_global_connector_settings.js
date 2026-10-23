frappe.ui.form.on("Karma Global Connector Settings", {
	refresh(frm) {
		frm.page.set_title(__("Karma Global Settings"));
		alaiy_os.connector_card.mount(frm, "karmaglobal");
		alaiy_os.connector_card.setup_password_reveal(frm, "kg_api_secret", "karmaglobal");

		frm.add_custom_button(
			__("Test Connection"),
			() =>
				frappe.call({
					// The registry wrapper also flips the status card to "Connected".
					method: "alaiy_os.api.connectors.test_connector",
					args: { connector_id: "karmaglobal" },
					callback(r) {
						const res = r.message || {};
						frappe.show_alert(
							{
								message: res.message || __(res.success ? "Connected" : "Connection failed"),
								indicator: res.success ? "green" : "red",
							},
							7,
						);
						frm.reload_doc();
					},
				}),
			__("Actions"),
		);

		for (const [label, method] of [
			[__("Sync Catalogue"), "trigger_catalogue_sync"],
			[__("Sync Inventory"), "trigger_inventory_sync"],
		]) {
			frm.add_custom_button(
				label,
				() =>
					frappe.call({
						method: `alaiy_os_connector_karmaglobal.api.sync.${method}`,
						callback: () =>
							frappe.show_alert({ message: __("{0} queued", [label]), indicator: "blue" }, 5),
					}),
				__("Actions"),
			);
		}
	},
});
