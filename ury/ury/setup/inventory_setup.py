"""
Setup script for Restaurant Inventory Management System
Creates required custom fields and configurations
"""

import frappe

def setup_inventory_management():
    """
    Setup all required custom fields and configurations for inventory management
    """
    try:
        # 1. Create custom field in POS Profile to enable/disable inventory deduction
        create_pos_profile_inventory_field()
        
        # 2. Create custom field in Stock Entry to link back to POS Invoice
        create_stock_entry_pos_link_field()
        
        # 3. Setup default item groups if needed
        setup_default_item_groups()
        
        frappe.db.commit()
        print("✅ Inventory Management setup completed successfully!")
        
    except Exception as e:
        frappe.log_error(f"Error in inventory setup: {str(e)}", "Inventory Setup Error")
        print(f"❌ Error in setup: {str(e)}")


def create_pos_profile_inventory_field():
    """Create custom field in POS Profile to enable inventory deduction"""
    if not frappe.db.exists("Custom Field", "POS Profile-custom_enable_inventory_deduction"):
        custom_field = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "POS Profile",
            "fieldname": "custom_enable_inventory_deduction",
            "label": "Enable Inventory Deduction",
            "fieldtype": "Check",
            "insert_after": "table_attention_time",
            "description": "Automatically deduct ingredients from stock based on BOM when invoice is submitted",
            "default": "0"
        })
        custom_field.insert()
        print("✅ Created POS Profile inventory deduction field")


def create_stock_entry_pos_link_field():
    """Create custom field in Stock Entry to link back to POS Invoice"""
    if not frappe.db.exists("Custom Field", "Stock Entry-custom_pos_invoice"):
        custom_field = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Stock Entry",
            "fieldname": "custom_pos_invoice",
            "label": "POS Invoice",
            "fieldtype": "Link",
            "options": "POS Invoice",
            "insert_after": "purchase_receipt_no",
            "description": "Link to POS Invoice that triggered this stock entry",
            "read_only": 1
        })
        custom_field.insert()
        print("✅ Created Stock Entry POS Invoice link field")


def setup_default_item_groups():
    """Setup default item groups for restaurant"""
    item_groups = [
        {"item_group_name": "Menu Items", "parent_item_group": "All Item Groups"},
        {"item_group_name": "Raw Materials", "parent_item_group": "All Item Groups"},
        {"item_group_name": "Beverages", "parent_item_group": "Menu Items"},
        {"item_group_name": "Main Course", "parent_item_group": "Menu Items"},
        {"item_group_name": "Appetizers", "parent_item_group": "Menu Items"},
        {"item_group_name": "Desserts", "parent_item_group": "Menu Items"}
    ]
    
    for group in item_groups:
        if not frappe.db.exists("Item Group", group["item_group_name"]):
            item_group_doc = frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": group["item_group_name"],
                "parent_item_group": group["parent_item_group"],
                "is_group": 0
            })
            item_group_doc.insert()
            print(f"✅ Created Item Group: {group['item_group_name']}")


@frappe.whitelist()
def run_setup():
    """API endpoint to run setup"""
    setup_inventory_management()
    return {"success": True, "message": "Inventory Management setup completed"}


if __name__ == "__main__":
    setup_inventory_management()

def setup_dashboard_workspace():
    """Setup Restaurant Dashboard workspace"""
    try:
        # Create workspace if it doesn't exist
        if not frappe.db.exists("Workspace", "Restaurant Dashboard"):
            workspace = frappe.get_doc({
                "doctype": "Workspace",
                "title": "Restaurant Dashboard",
                "name": "Restaurant Dashboard",
                "module": "URY",
                "icon": "restaurant",
                "color": "#FF6B35",
                "public": 1,
                "content": json.dumps([
                    {
                        "type": "header",
                        "data": {
                            "text": "📊 Restaurant Analytics",
                            "col": 12
                        }
                    },
                    {
                        "type": "shortcut",
                        "data": {
                            "shortcut_name": "Dashboard Overview",
                            "label": "Dashboard Overview",
                            "link_to": "/app/restaurant_dashboard",
                            "type": "URL",
                            "icon": "dashboard",
                            "color": "#FF6B35",
                            "col": 4
                        }
                    },
                    {
                        "type": "shortcut",
                        "data": {
                            "shortcut_name": "Dashboard Report",
                            "label": "Dashboard Report",
                            "link_to": "Restaurant Dashboard Summary",
                            "type": "Report",
                            "icon": "report",
                            "color": "#4CAF50",
                            "col": 4
                        }
                    },
                    {
                        "type": "shortcut",
                        "data": {
                            "shortcut_name": "Inventory Status",
                            "label": "Inventory Status",
                            "link_to": "Stock Ledger",
                            "type": "Report",
                            "icon": "stock",
                            "color": "#2196F3",
                            "col": 4
                        }
                    },
                    {
                        "type": "header",
                        "data": {
                            "text": "🍽️ Menu Management",
                            "col": 12
                        }
                    },
                    {
                        "type": "shortcut",
                        "data": {
                            "shortcut_name": "Menu Items",
                            "label": "Menu Items",
                            "link_to": "Item",
                            "type": "DocType",
                            "icon": "item",
                            "color": "#FF9800",
                            "col": 3
                        }
                    },
                    {
                        "type": "shortcut",
                        "data": {
                            "shortcut_name": "Recipes (BOM)",
                            "label": "Recipes (BOM)",
                            "link_to": "BOM",
                            "type": "DocType",
                            "icon": "bom",
                            "color": "#9C27B0",
                            "col": 3
                        }
                    },
                    {
                        "type": "shortcut",
                        "data": {
                            "shortcut_name": "Stock Entries",
                            "label": "Stock Entries",
                            "link_to": "Stock Entry",
                            "type": "DocType",
                            "icon": "stock-entry",
                            "color": "#607D8B",
                            "col": 3
                        }
                    },
                    {
                        "type": "shortcut",
                        "data": {
                            "shortcut_name": "POS Invoices",
                            "label": "POS Invoices",
                            "link_to": "POS Invoice",
                            "type": "DocType",
                            "icon": "pos",
                            "color": "#795548",
                            "col": 3
                        }
                    }
                ])
            })
            workspace.insert()
            print("✅ Created Restaurant Dashboard workspace")
        
    except Exception as e:
        frappe.log_error(f"Error creating dashboard workspace: {str(e)}", "Dashboard Setup Error")
        print(f"❌ Error creating workspace: {str(e)}")


@frappe.whitelist()
def setup_complete_dashboard():
    """Complete dashboard setup including workspace"""
    setup_inventory_management()
    setup_dashboard_workspace()
    return {"success": True, "message": "Complete dashboard setup completed"}