import frappe
from datetime import datetime
from frappe.utils import now_datetime, get_time,now


def before_insert(doc, method):
    pos_invoice_naming(doc, method)
    order_type_update(doc, method)
    restrict_existing_order(doc, method)


def after_insert(doc, method):
    deduct_ingredients_from_stock(doc, method)


def validate(doc, method):
    validate_invoice(doc, method)
    validate_customer(doc, method)
    validate_price_list(doc, method)


def before_submit(doc, method):
    calculate_and_set_times(doc, method)
    validate_invoice_print(doc, method)
    ro_reload_submit(doc, method)


def on_trash(doc, method):
    table_status_delete(doc, method)
    restore_ingredients_to_stock(doc, method)


def validate_invoice(doc, method):
    if doc.waiter == None or doc.waiter == "":
        doc.waiter = doc.modified_by
    remove_items = frappe.db.get_value("POS Profile", doc.pos_profile, "remove_items")
    
    if doc.invoice_printed == 1 and remove_items == 0:
        # Get the original items from db
        original_doc = frappe.get_doc("POS Invoice", doc.name)
        
        # Create dictionaries to store both quantities and names
        original_items = {
            item.item_code: {"qty": item.qty, "name": item.item_name} 
            for item in original_doc.items
        }
        current_items = {
            item.item_code: {"qty": item.qty, "name": item.item_name} 
            for item in doc.items
        }
          
        # Check for removed items
        removed_items = set(original_items.keys()) - set(current_items.keys())
        
        # Check for quantity reductions
        reduced_qty_items = []
        for item_code, item_data in original_items.items():
            if (item_code in current_items and 
                current_items[item_code]["qty"] < item_data["qty"]):
                reduced_qty_items.append(
                    f"{item_data['name']} (qty reduced from {item_data['qty']} "
                    f"to {current_items[item_code]['qty']})"
                )
        
        if removed_items or reduced_qty_items:
            error_msg = []
            if removed_items:
                removed_item_names = [
                    original_items[item_code]["name"] 
                    for item_code in removed_items
                ]
                error_msg.append(f"Removed items: {', '.join(removed_item_names)}")
            if reduced_qty_items:
                error_msg.append(f"Modified quantities: {', '.join(reduced_qty_items)}")
                
            frappe.throw(
                ("Cannot modify items after invoice is printed.\n{0}")
                .format("\n".join(error_msg))
            )


def validate_customer(doc, method):
    if doc.customer_name == None or doc.customer_name == "":
        frappe.throw(
            (" Failed to load data , Please Refresh the page ").format(
                doc.customer_name
            )
        )


def calculate_and_set_times(doc, method):
    doc.arrived_time = doc.creation

    current_time_str = now()
    
    current_time = datetime.strptime(current_time_str, "%Y-%m-%d %H:%M:%S.%f")
    
    time_difference = current_time - doc.creation
    
    total_seconds = int(time_difference.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    formatted_spend_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    doc.total_spend_time = formatted_spend_time


def validate_invoice_print(doc, method):
    # Check if the invoice has been printed
    invoice_printed = frappe.db.get_value("POS Invoice", doc.name, "invoice_printed")

    # If the invoice is associated with a restaurant table and hasn't been printed
    if doc.restaurant_table and invoice_printed == 0:
        frappe.throw(
            "Printing the invoice is mandatory before submitting. Please print the invoice."
        )


def table_status_delete(doc, method):
    if doc.restaurant_table:
        frappe.db.set_value(
            "URY Table",
            doc.restaurant_table,
            {"occupied": 0, "latest_invoice_time": None},
        )


def pos_invoice_naming(doc, method):
    pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)
    restaurant = pos_profile.restaurant

    if not doc.restaurant_table:
        doc.naming_series = frappe.db.get_value(
            "URY Restaurant", restaurant, "invoice_series_prefix"
        )
        
        if doc.order_type == "Aggregators":
            doc.naming_series = frappe.db.get_value(
                "URY Restaurant", restaurant, "aggregator_series_prefix"
            )
    


def order_type_update(doc, method):
    if doc.restaurant_table:
        if not doc.order_type:
            is_take_away = frappe.db.get_value(
                "URY Table", doc.restaurant_table, "is_take_away"
            )
            if is_take_away == 1:
                doc.order_type = "Take Away"
            else:
                doc.order_type = "Dine In"
    


# reload restaurant order page if submitted invoice is open there
def ro_reload_submit(doc, method):
    frappe.publish_realtime("reload_ro", {"name": doc.name})


def validate_price_list(doc, method):
        
    if doc.restaurant:
        
        if doc.restaurant_table:
            room = frappe.db.get_value("URY Table", doc.restaurant_table, "restaurant_room")
            menu_name = (
                frappe.db.get_value("URY Restaurant", doc.restaurant, "active_menu")
                if not frappe.db.get_value(
                    "URY Restaurant", doc.restaurant, "room_wise_menu"
                )
                else frappe.db.get_value(
                    "Menu for Room", {"parent": doc.restaurant, "room": room}, "menu"
                )
            )

            doc.selling_price_list = frappe.db.get_value(
                "Price List", dict(restaurant_menu=menu_name, enabled=1)
            )
        
        if doc.order_type == "Aggregators":
            price_list = frappe.db.get_value("Aggregator Settings",
                {"customer": doc.customer, "parent": doc.branch, "parenttype": "Branch"},
                "price_list",
                )
            
            if not price_list:
                frappe.throw(f"Price list for customer {doc.customer} in branch {doc.branch} not found in Aggregator Settings.")
                
            doc.selling_price_list = price_list
            
        else:
            menu_name = frappe.db.get_value("URY Restaurant", doc.restaurant, "active_menu") 

            doc.selling_price_list = frappe.db.get_value(
                "Price List", dict(restaurant_menu=menu_name, enabled=1)
            )
            

def restrict_existing_order(doc, event):
    if doc.restaurant_table:
        invoice_exist = frappe.db.exists(
            "POS Invoice",
            {
                "restaurant_table": doc.restaurant_table,
                "docstatus": 0,
                "invoice_printed": 0,
            },
        )
        if invoice_exist:
            frappe.throw(
                ("Table {0} has an existing invoice").format(doc.restaurant_table)
            )


def deduct_ingredients_from_stock(doc, method):
    """
    Deduct ingredients from stock using ERPNext Manufacturing logic
    Creates Stock Entry (Material Consumption for Manufacture) for each menu item with BOM
    """
    try:
        # Check if inventory deduction is enabled for this POS Profile
        enable_inventory_deduction = frappe.db.get_value("POS Profile", doc.pos_profile, "custom_enable_inventory_deduction")
        if not enable_inventory_deduction:
            return
            
        # Get the default warehouse for the branch/restaurant
        warehouse = get_default_warehouse(doc)
        if not warehouse:
            frappe.log_error(f"No default warehouse found for POS Invoice {doc.name}", "Stock Deduction Error")
            return
        
        # Import ERPNext BOM functions
        from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
        
        # Process each menu item that has a BOM
        for item in doc.items:
            # Get the BOM for this item
            bom = frappe.db.get_value("BOM", 
                {"item": item.item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, 
                "name")
            
            if bom:
                # Use ERPNext's BOM explosion to get all raw materials
                bom_items = get_bom_items_as_dict(
                    bom=bom,
                    company=doc.company,
                    qty=item.qty,  # Quantity sold
                    fetch_exploded=1,  # Get sub-assembly items too
                    fetch_scrap_items=0
                )
                
                if bom_items:
                    create_manufacturing_stock_entry(doc, item, bom_items, warehouse)
            
    except Exception as e:
        frappe.log_error(f"Error in deduct_ingredients_from_stock for POS Invoice {doc.name}: {str(e)}", "Stock Deduction Error")
        # Don't throw error to avoid blocking invoice submission


def get_default_warehouse(doc):
    """
    Get the default warehouse for stock deduction
    Priority: POS Profile warehouse > Branch warehouse > Company default warehouse
    """
    # Try to get warehouse from POS Profile
    warehouse = frappe.db.get_value("POS Profile", doc.pos_profile, "warehouse")
    
    if not warehouse:
        # Try to get from Branch (if custom field exists)
        warehouse = frappe.db.get_value("Branch", doc.branch, "custom_default_warehouse")
    
    if not warehouse:
        # Get company's default warehouse
        company = frappe.db.get_value("POS Profile", doc.pos_profile, "company")
        warehouse = frappe.db.get_value("Company", company, "default_warehouse")
    
    return warehouse


def create_manufacturing_stock_entry(pos_invoice, menu_item, bom_items, warehouse):
    """
    Create Stock Entry (Material Issue) for restaurant orders
    Since POS Invoice is in draft state, we use Material Issue instead of Manufacturing
    """
    try:
        # Create Stock Entry document
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.purpose = "Material Issue"
        stock_entry.company = pos_invoice.company
        stock_entry.posting_date = pos_invoice.posting_date
        stock_entry.posting_time = pos_invoice.posting_time
        
        # Set reference to POS Invoice
        stock_entry.custom_pos_invoice = pos_invoice.name  # Custom field to link back
        
        # Add raw materials (ingredients) that are being consumed
        # Note: For restaurant orders, we only deduct ingredients, not produce finished items
        for item_code, bom_item in bom_items.items():
            # Check available stock
            available_qty = frappe.db.get_value("Bin", 
                {"item_code": item_code, "warehouse": warehouse}, 
                "actual_qty") or 0
            
            required_qty = bom_item.qty
            
            if available_qty >= required_qty:
                stock_entry.append("items", {
                    "item_code": item_code,
                    "item_name": bom_item.item_name,
                    "qty": required_qty,
                    "uom": bom_item.uom,
                    "s_warehouse": warehouse,  # Source warehouse (where raw materials come from)
                    "basic_rate": bom_item.rate or 0,
                    "allow_zero_valuation_rate": 1
                })
            else:
                # Log insufficient stock warning
                frappe.log_error(
                    f"Insufficient stock for {bom_item.item_name} ({item_code}). "
                    f"Required: {required_qty}, Available: {available_qty}. "
                    f"POS Invoice: {pos_invoice.name}",
                    "Insufficient Stock Warning"
                )
        
        # Only create if we have raw materials to consume
        if stock_entry.items:
            # Calculate total food cost
            total_food_cost = sum(item.qty * (item.basic_rate or 0) for item in stock_entry.items)
            
            stock_entry.insert()
            stock_entry.submit()
            
            # Add comment to POS Invoice
            pos_invoice.add_comment("Comment", 
                f"Ingredient Stock Entry {stock_entry.name} created for {menu_item.item_name} "
                f"(Qty: {menu_item.qty}). Food Cost: {total_food_cost:.2f}")
            
            return stock_entry.name
            
    except Exception as e:
        frappe.log_error(f"Error creating Manufacturing Stock Entry for POS Invoice {pos_invoice.name}, Item {menu_item.item_code}: {str(e)}", "Manufacturing Stock Entry Error")
        return None

def restore_ingredients_to_stock(doc, method):
    """
    Cancel related Stock Entries when POS Invoice is cancelled or deleted
    ERPNext will automatically reverse the stock movements
    """
    try:
        # Check if inventory deduction is enabled for this POS Profile
        enable_inventory_deduction = frappe.db.get_value("POS Profile", doc.pos_profile, "custom_enable_inventory_deduction")
        if not enable_inventory_deduction:
            return
            
        # Restore for both cancellation and deletion
        # method == "on_trash" means deletion, doc.docstatus == 2 means cancellation
        
        # Find all Stock Entries linked to this POS Invoice
        stock_entries = frappe.db.get_all("Stock Entry", 
            filters={
                "custom_pos_invoice": doc.name,
                "docstatus": 1,  # Submitted
                "stock_entry_type": "Material Issue"
            },
            fields=["name"]
        )
        
        # Cancel all related Stock Entries
        for se in stock_entries:
            try:
                stock_entry_doc = frappe.get_doc("Stock Entry", se.name)
                stock_entry_doc.cancel()
                
                # Add comment to POS Invoice
                doc.add_comment("Comment", f"Stock Entry {se.name} cancelled due to POS Invoice cancellation")
                
            except Exception as se_error:
                frappe.log_error(f"Error cancelling Stock Entry {se.name} for POS Invoice {doc.name}: {str(se_error)}", "Stock Entry Cancellation Error")
            
    except Exception as e:
        frappe.log_error(f"Error in restore_ingredients_to_stock for POS Invoice {doc.name}: {str(e)}", "Stock Restoration Error")



def on_update_after_submit(doc, method):
    """
    Handle inventory adjustments when POS Invoice items are modified after creation
    This is called when items are added/removed from existing orders
    """
    try:
        # Check if inventory deduction is enabled
        enable_inventory_deduction = frappe.db.get_value("POS Profile", doc.pos_profile, "custom_enable_inventory_deduction")
        if not enable_inventory_deduction:
            return
        
        # Get original document from database
        original_doc = frappe.get_doc("POS Invoice", doc.name)
        
        # Compare items and handle differences
        handle_inventory_adjustments(original_doc, doc)
        
    except Exception as e:
        frappe.log_error(f"Error in on_update_after_submit for POS Invoice {doc.name}: {str(e)}", "Inventory Adjustment Error")


def handle_inventory_adjustments(original_doc, updated_doc):
    """
    Handle inventory adjustments when order items change
    """
    try:
        # Create dictionaries for easy comparison
        original_items = {item.item_code: item.qty for item in original_doc.items}
        updated_items = {item.item_code: item.qty for item in updated_doc.items}
        
        warehouse = get_default_warehouse(updated_doc)
        if not warehouse:
            return
        
        from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
        
        # Handle removed items (restore stock)
        for item_code, original_qty in original_items.items():
            if item_code not in updated_items:
                # Item completely removed - restore full quantity
                restore_item_ingredients(updated_doc, item_code, original_qty, warehouse)
        
        # Handle added items (deduct stock)
        for item_code, updated_qty in updated_items.items():
            if item_code not in original_items:
                # New item added - deduct full quantity
                deduct_item_ingredients(updated_doc, item_code, updated_qty, warehouse)
        
        # Handle quantity changes
        for item_code in set(original_items.keys()) & set(updated_items.keys()):
            qty_difference = updated_items[item_code] - original_items[item_code]
            if qty_difference > 0:
                # Quantity increased - deduct additional ingredients
                deduct_item_ingredients(updated_doc, item_code, qty_difference, warehouse)
            elif qty_difference < 0:
                # Quantity decreased - restore excess ingredients
                restore_item_ingredients(updated_doc, item_code, abs(qty_difference), warehouse)
        
    except Exception as e:
        frappe.log_error(f"Error handling inventory adjustments: {str(e)}", "Inventory Adjustment Error")


def deduct_item_ingredients(pos_invoice, item_code, qty, warehouse):
    """Helper function to deduct ingredients for a specific item"""
    try:
        bom = frappe.db.get_value("BOM", 
            {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, 
            "name")
        
        if bom:
            from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
            bom_items = get_bom_items_as_dict(bom=bom, company=pos_invoice.company, qty=qty, fetch_exploded=1)
            
            if bom_items:
                # Create a mock item object for the function
                mock_item = frappe._dict({
                    "item_code": item_code,
                    "item_name": frappe.db.get_value("Item", item_code, "item_name"),
                    "qty": qty,
                    "uom": "Nos",
                    "rate": 0
                })
                create_manufacturing_stock_entry(pos_invoice, mock_item, bom_items, warehouse)
                
    except Exception as e:
        frappe.log_error(f"Error deducting ingredients for {item_code}: {str(e)}", "Ingredient Deduction Error")


def restore_item_ingredients(pos_invoice, item_code, qty, warehouse):
    """Helper function to restore ingredients for a specific item"""
    try:
        bom = frappe.db.get_value("BOM", 
            {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, 
            "name")
        
        if bom:
            from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
            bom_items = get_bom_items_as_dict(bom=bom, company=pos_invoice.company, qty=qty, fetch_exploded=1)
            
            if bom_items:
                # Create Material Receipt to restore ingredients
                stock_entry = frappe.new_doc("Stock Entry")
                stock_entry.stock_entry_type = "Material Receipt"
                stock_entry.purpose = "Material Receipt"
                stock_entry.company = pos_invoice.company
                stock_entry.custom_pos_invoice = pos_invoice.name
                
                for item_code_bom, bom_item in bom_items.items():
                    stock_entry.append("items", {
                        "item_code": item_code_bom,
                        "item_name": bom_item.item_name,
                        "qty": bom_item.qty,
                        "uom": bom_item.uom,
                        "t_warehouse": warehouse,
                        "basic_rate": bom_item.rate or 0,
                        "allow_zero_valuation_rate": 1
                    })
                
                if stock_entry.items:
                    stock_entry.insert()
                    stock_entry.submit()
                    
                    pos_invoice.add_comment("Comment", 
                        f"Ingredient restoration Stock Entry {stock_entry.name} created for {item_code} (Qty: {qty})")
                
    except Exception as e:
        frappe.log_error(f"Error restoring ingredients for {item_code}: {str(e)}", "Ingredient Restoration Error")