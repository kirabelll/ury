import frappe

def get_context(context):
    context.no_cache = 1
    context.title = "Restaurant Dashboard"
    
    # Check permissions
    if not frappe.has_permission("POS Invoice", "read"):
        frappe.throw("Not permitted", frappe.PermissionError)
    
    return context