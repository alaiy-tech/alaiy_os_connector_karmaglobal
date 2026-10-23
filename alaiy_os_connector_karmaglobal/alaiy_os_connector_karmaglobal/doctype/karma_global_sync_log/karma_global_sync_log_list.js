const KG_COLORS = {
	catalogue: "blue",
	inventory: "orange",
	scheduled: "purple",
	manual: "pink",
	queued: "grey",
	running: "blue",
	success: "green",
	failed: "red",
	skipped: "yellow",
};

function kg_pill(value) {
	if (!value) return "";
	return `<span class="indicator-pill ${KG_COLORS[value] || "darkgrey"} filterable" data-filter="=,${value}">
		<span>${frappe.utils.escape_html(value)}</span>
	</span>`;
}

frappe.listview_settings["Karma Global Sync Log"] = {
	get_indicator(doc) {
		return [__(doc.status), KG_COLORS[doc.status] || "darkgrey", `status,=,${doc.status}`];
	},
	formatters: { sync_type: kg_pill, trigger: kg_pill, status: kg_pill },
};
