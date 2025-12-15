import frappe
from datetime import datetime
from frappe.utils import now_datetime, get_time,now


def before_insert(doc, method):
    pos_invoice_naming(doc, method)
    order_type_update(doc, method)
    restrict_existing_order(doc, method)


def validate(doc, method):
    validate_invoice(doc, method)
    validate_customer(doc, method)
    validate_price_list(doc, method)


def before_submit(doc, method):
    calculate_and_set_times(doc, method)
    validate_invoice_print(doc, method)
    ro_reload_submit(doc, method)
    deduct_ingredients_from_stock(doc, method)


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
    Deduct ingredients from stock based on BOM (recipe) when POS Invoice is submitted
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
        
        # Collect all ingredients to deduct
        ingredients_to_deduct = []
        
        for item in doc.items:
            # Get the BOM for this item
            bom = frappe.db.get_value("BOM", 
                {"item": item.item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, 
                "name")
            
            if bom:
                # Get BOM details
                bom_doc = frappe.get_doc("BOM", bom)
                
                # Calculate ingredient quantities based on sold quantity
                for bom_item in bom_doc.items:
                    # Calculate required quantity: (BOM qty / BOM output qty) * sold qty
                    required_qty = (bom_item.qty / bom_doc.quantity) * item.qty
                    
                    # Handle UOM conversion if needed
                    stock_uom = frappe.db.get_value("Item", bom_item.item_code, "stock_uom")
                    final_qty = required_qty
                    final_uom = bom_item.uom
                    
                    if stock_uom != bom_item.uom:
                        # Convert to stock UOM for inventory deduction
                        conversion_result = convert_uom_for_deduction(required_qty, bom_item.uom, stock_uom, bom_item.item_code)
                        if conversion_result["success"]:
                            final_qty = conversion_result["converted_qty"]
                            final_uom = stock_uom
                    
                    # Add to ingredients list
                    ingredient_key = f"{bom_item.item_code}_{warehouse}"
                    
                    # If ingredient already exists, add to quantity
                    existing_ingredient = next((ing for ing in ingredients_to_deduct 
                                              if ing["item_code"] == bom_item.item_code and ing["warehouse"] == warehouse), None)
                    
                    if existing_ingredient:
                        existing_ingredient["qty"] += final_qty
                    else:
                        ingredients_to_deduct.append({
                            "item_code": bom_item.item_code,
                            "item_name": bom_item.item_name,
                            "qty": final_qty,
                            "warehouse": warehouse,
                            "uom": final_uom,
                            "original_qty": required_qty,
                            "original_uom": bom_item.uom
                        })
        
        # Create Stock Entry if there are ingredients to deduct
        if ingredients_to_deduct:
            create_stock_entry_for_ingredients(doc, ingredients_to_deduct, warehouse)
            
    except Exception as e:
        frappe.log_error(f"Error in deduct_ingredients_from_stock for POS Invoice {doc.name}: {str(e)}", "Stock Deduction Error")
        # Don't throw error to avoid blocking invoice submission
        # frappe.throw(f"Error deducting ingredients from stock: {str(e)}")


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


def create_stock_entry_for_ingredients(pos_invoice, ingredients, warehouse):
    """
    Create a Stock Entry to deduct ingredients from inventory
    """
    try:
        # Create Stock Entry document
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.purpose = "Material Issue"
        stock_entry.company = frappe.db.get_value("POS Profile", pos_invoice.pos_profile, "company")
        stock_entry.posting_date = pos_invoice.posting_date
        stock_entry.posting_time = pos_invoice.posting_time
        
        # Add reference to POS Invoice
        stock_entry.add_comment("Comment", f"Automatic ingredient deduction for POS Invoice: {pos_invoice.name}")
        
        # Add items to Stock Entry
        for ingredient in ingredients:
            # Check if item has stock
            stock_qty = frappe.db.get_value("Bin", 
                {"item_code": ingredient["item_code"], "warehouse": warehouse}, 
                "actual_qty") or 0
            
            if stock_qty >= ingredient["qty"]:
                stock_entry.append("items", {
                    "item_code": ingredient["item_code"],
                    "item_name": ingredient["item_name"],
                    "qty": ingredient["qty"],
                    "uom": ingredient["uom"],
                    "s_warehouse": warehouse,
                    "basic_rate": frappe.db.get_value("Item Price", 
                        {"item_code": ingredient["item_code"]}, "price_list_rate") or 0
                })
            else:
                # Log insufficient stock but don't block the process
                frappe.log_error(
                    f"Insufficient stock for {ingredient['item_name']} ({ingredient['item_code']}). "
                    f"Required: {ingredient['qty']}, Available: {stock_qty}",
                    "Insufficient Stock Warning"
                )
        
        # Submit Stock Entry if there are items
        if stock_entry.items:
            stock_entry.insert()
            stock_entry.submit()
            
            # Add a comment to POS Invoice about the stock entry
            pos_invoice.add_comment("Comment", f"Stock Entry {stock_entry.name} created for ingredient deduction")
            
    except Exception as e:
        frappe.log_error(f"Error creating Stock Entry for POS Invoice {pos_invoice.name}: {str(e)}", "Stock Entry Creation Error")
        # Don't throw error to avoid blocking invoice submission

def restore_ingredients_to_stock(doc, method):
    """
    Restore ingredients to stock when POS Invoice is cancelled/deleted
    """
    try:
        # Check if inventory deduction is enabled for this POS Profile
        enable_inventory_deduction = frappe.db.get_value("POS Profile", doc.pos_profile, "custom_enable_inventory_deduction")
        if not enable_inventory_deduction:
            return
            
        # Only restore if the invoice was submitted (had stock deducted)
        if doc.docstatus != 2:  # 2 = Cancelled
            return
            
        # Get the default warehouse
        warehouse = get_default_warehouse(doc)
        if not warehouse:
            return
        
        # Collect all ingredients to restore
        ingredients_to_restore = []
        
        for item in doc.items:
            # Get the BOM for this item
            bom = frappe.db.get_value("BOM", 
                {"item": item.item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, 
                "name")
            
            if bom:
                # Get BOM details
                bom_doc = frappe.get_doc("BOM", bom)
                
                # Calculate ingredient quantities that were deducted
                for bom_item in bom_doc.items:
                    required_qty = (bom_item.qty / bom_doc.quantity) * item.qty
                    
                    # Add to ingredients list
                    existing_ingredient = next((ing for ing in ingredients_to_restore 
                                              if ing["item_code"] == bom_item.item_code), None)
                    
                    if existing_ingredient:
                        existing_ingredient["qty"] += required_qty
                    else:
                        ingredients_to_restore.append({
                            "item_code": bom_item.item_code,
                            "item_name": bom_item.item_name,
                            "qty": required_qty,
                            "warehouse": warehouse,
                            "uom": bom_item.uom
                        })
        
        # Create Stock Entry to restore ingredients
        if ingredients_to_restore:
            create_stock_entry_for_restoration(doc, ingredients_to_restore, warehouse)
            
    except Exception as e:
        frappe.log_error(f"Error in restore_ingredients_to_stock for POS Invoice {doc.name}: {str(e)}", "Stock Restoration Error")


def create_stock_entry_for_restoration(pos_invoice, ingredients, warehouse):
    """
    Create a Stock Entry to restore ingredients to inventory when invoice is cancelled
    """
    try:
        # Create Stock Entry document
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Receipt"
        stock_entry.purpose = "Material Receipt"
        stock_entry.company = frappe.db.get_value("POS Profile", pos_invoice.pos_profile, "company")
        
        # Add reference to POS Invoice
        stock_entry.add_comment("Comment", f"Automatic ingredient restoration for cancelled POS Invoice: {pos_invoice.name}")
        
        # Add items to Stock Entry
        for ingredient in ingredients:
            stock_entry.append("items", {
                "item_code": ingredient["item_code"],
                "item_name": ingredient["item_name"],
                "qty": ingredient["qty"],
                "uom": ingredient["uom"],
                "t_warehouse": warehouse,
                "basic_rate": frappe.db.get_value("Item Price", 
                    {"item_code": ingredient["item_code"]}, "price_list_rate") or 0
            })
        
        # Submit Stock Entry
        if stock_entry.items:
            stock_entry.insert()
            stock_entry.submit()
            
    except Exception as e:
        frappe.log_error(f"Error creating restoration Stock Entry for POS Invoice {pos_invoice.name}: {str(e)}", "Stock Restoration Error")

def convert_uom_for_deduction(qty, from_uom, to_uom, item_code):
    """
    Convert UOM for inventory deduction - simplified version
    """
    try:
        # Common conversions
        conversions = {
            ("Liter", "ml"): 1000,
            ("Liter", "Milliliter"): 1000,
            ("Kg", "grams"): 1000,
            ("Kg", "Gram"): 1000,
            ("Kilogram", "Gram"): 1000,
            ("Meter", "cm"): 100,
            ("Meter", "Centimeter"): 100,
        }
        
        conversion_key = (from_uom, to_uom)
        if conversion_key in conversions:
            return {
                "success": True,
                "converted_qty": qty * conversions[conversion_key]
            }
        
        # Check ERPNext UOM conversion
        uom_conversion = frappe.db.get_value("UOM Conversion Detail", {
            "parent": item_code,
            "uom": to_uom
        }, "conversion_factor")
        
        if uom_conversion:
            return {
                "success": True,
                "converted_qty": qty * uom_conversion
            }
        
        # If same UOM or no conversion found, return original
        return {"success": True, "converted_qty": qty}
        
    except Exception:
        return {"success": True, "converted_qty": qty}  # Fallback to original qty