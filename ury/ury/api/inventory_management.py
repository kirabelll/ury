"""
Inventory Management API for URY Restaurant System
Handles automatic ingredient deduction based on recipes (BOMs)
"""

import frappe
from frappe import _

@frappe.whitelist()
def get_bom_ingredients(item_code):
    """
    Get all ingredients for a menu item from its BOM
    """
    try:
        bom = frappe.db.get_value("BOM", 
            {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, 
            "name")
        
        if not bom:
            return {"success": False, "message": f"No active BOM found for item {item_code}"}
        
        bom_doc = frappe.get_doc("BOM", bom)
        ingredients = []
        
        for item in bom_doc.items:
            ingredients.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
                "uom": item.uom,
                "rate": item.rate or 0
            })
        
        return {
            "success": True,
            "bom_name": bom,
            "output_qty": bom_doc.quantity,
            "ingredients": ingredients
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting BOM ingredients for {item_code}: {str(e)}", "BOM Ingredients Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def check_ingredient_stock(item_code, warehouse, required_qty):
    """
    Check if sufficient stock is available for an ingredient
    """
    try:
        available_qty = frappe.db.get_value("Bin", 
            {"item_code": item_code, "warehouse": warehouse}, 
            "actual_qty") or 0
        
        return {
            "item_code": item_code,
            "available_qty": available_qty,
            "required_qty": required_qty,
            "sufficient": available_qty >= required_qty,
            "shortage": max(0, required_qty - available_qty)
        }
        
    except Exception as e:
        return {"error": str(e)}


@frappe.whitelist()
def get_menu_items_with_bom():
    """
    Get all menu items that have BOMs (recipes)
    """
    try:
        items_with_bom = frappe.db.sql("""
            SELECT DISTINCT 
                b.item as item_code,
                i.item_name,
                b.name as bom_name,
                b.quantity as output_qty
            FROM `tabBOM` b
            INNER JOIN `tabItem` i ON b.item = i.item_code
            WHERE b.is_active = 1 
            AND b.is_default = 1 
            AND b.docstatus = 1
            AND i.is_sales_item = 1
            ORDER BY i.item_name
        """, as_dict=True)
        
        return {"success": True, "items": items_with_bom}
        
    except Exception as e:
        frappe.log_error(f"Error getting menu items with BOM: {str(e)}", "Menu Items BOM Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def simulate_ingredient_deduction(pos_invoice_name):
    """
    Simulate ingredient deduction without actually creating stock entries
    Useful for testing and validation
    """
    try:
        pos_invoice = frappe.get_doc("POS Invoice", pos_invoice_name)
        warehouse = get_default_warehouse_for_simulation(pos_invoice)
        
        if not warehouse:
            return {"success": False, "message": "No default warehouse found"}
        
        simulation_results = []
        
        for item in pos_invoice.items:
            bom = frappe.db.get_value("BOM", 
                {"item": item.item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, 
                "name")
            
            if bom:
                bom_doc = frappe.get_doc("BOM", bom)
                item_ingredients = []
                
                for bom_item in bom_doc.items:
                    required_qty = (bom_item.qty / bom_doc.quantity) * item.qty
                    available_qty = frappe.db.get_value("Bin", 
                        {"item_code": bom_item.item_code, "warehouse": warehouse}, 
                        "actual_qty") or 0
                    
                    item_ingredients.append({
                        "ingredient_code": bom_item.item_code,
                        "ingredient_name": bom_item.item_name,
                        "required_qty": required_qty,
                        "available_qty": available_qty,
                        "sufficient": available_qty >= required_qty,
                        "uom": bom_item.uom
                    })
                
                simulation_results.append({
                    "menu_item": item.item_name,
                    "menu_item_code": item.item_code,
                    "sold_qty": item.qty,
                    "bom_name": bom,
                    "ingredients": item_ingredients
                })
        
        return {"success": True, "warehouse": warehouse, "results": simulation_results}
        
    except Exception as e:
        return {"success": False, "message": str(e)}


def get_default_warehouse_for_simulation(pos_invoice):
    """Helper function for simulation"""
    warehouse = frappe.db.get_value("POS Profile", pos_invoice.pos_profile, "warehouse")
    
    if not warehouse:
        warehouse = frappe.db.get_value("Branch", pos_invoice.branch, "custom_default_warehouse")
    
    if not warehouse:
        company = frappe.db.get_value("POS Profile", pos_invoice.pos_profile, "company")
        warehouse = frappe.db.get_value("Company", company, "default_warehouse")
    
    return warehouse


@frappe.whitelist()
def create_menu_item_from_bom(bom_name, item_group="Products", selling_price=0):
    """
    Create a menu item (sales item) from an existing BOM
    """
    try:
        bom_doc = frappe.get_doc("BOM", bom_name)
        
        # Check if item already exists
        if frappe.db.exists("Item", bom_doc.item):
            item_doc = frappe.get_doc("Item", bom_doc.item)
            # Update to make it a sales item if not already
            if not item_doc.is_sales_item:
                item_doc.is_sales_item = 1
                item_doc.save()
            return {"success": True, "message": f"Item {bom_doc.item} already exists and updated as sales item", "item_code": bom_doc.item}
        
        # Create new menu item
        item_doc = frappe.new_doc("Item")
        item_doc.item_code = bom_doc.item
        item_doc.item_name = bom_doc.item_name or bom_doc.item
        item_doc.item_group = item_group
        item_doc.stock_uom = bom_doc.uom
        item_doc.is_sales_item = 1
        item_doc.is_stock_item = 0  # Menu items are typically non-stock
        item_doc.has_batch_no = 0
        item_doc.has_serial_no = 0
        item_doc.description = f"Menu item created from BOM: {bom_name}"
        
        # Insert the item
        item_doc.insert()
        
        # Create item price if selling price is provided
        if selling_price > 0:
            create_item_price(item_doc.item_code, selling_price)
        
        return {
            "success": True, 
            "message": f"Menu item {item_doc.item_code} created successfully",
            "item_code": item_doc.item_code,
            "bom_name": bom_name
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating menu item from BOM {bom_name}: {str(e)}", "Menu Item Creation Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def create_item_price(item_code, price, price_list="Standard Selling"):
    """
    Create item price for a menu item
    """
    try:
        # Check if price already exists
        existing_price = frappe.db.exists("Item Price", {
            "item_code": item_code,
            "price_list": price_list
        })
        
        if existing_price:
            # Update existing price
            price_doc = frappe.get_doc("Item Price", existing_price)
            price_doc.price_list_rate = price
            price_doc.save()
            return {"success": True, "message": f"Price updated for {item_code}"}
        else:
            # Create new price
            price_doc = frappe.new_doc("Item Price")
            price_doc.item_code = item_code
            price_doc.price_list = price_list
            price_doc.price_list_rate = price
            price_doc.insert()
            return {"success": True, "message": f"Price created for {item_code}"}
            
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def convert_uom_quantity(from_qty, from_uom, to_uom, item_code=None):
    """
    Convert quantity from one UOM to another
    Example: 1 Liter = 1000 ml, 1 Kg = 1000 grams
    """
    try:
        # Common UOM conversions
        uom_conversions = {
            # Volume conversions
            ("Liter", "ml"): 1000,
            ("Liter", "Milliliter"): 1000,
            ("ml", "Liter"): 0.001,
            ("Milliliter", "Liter"): 0.001,
            
            # Weight conversions
            ("Kg", "grams"): 1000,
            ("Kg", "Gram"): 1000,
            ("Kilogram", "Gram"): 1000,
            ("grams", "Kg"): 0.001,
            ("Gram", "Kg"): 0.001,
            ("Gram", "Kilogram"): 0.001,
            
            # Length conversions
            ("Meter", "cm"): 100,
            ("Meter", "Centimeter"): 100,
            ("cm", "Meter"): 0.01,
            ("Centimeter", "Meter"): 0.01,
            
            # Same UOM
            ("Nos", "Nos"): 1,
            ("Each", "Each"): 1,
            ("Piece", "Piece"): 1,
        }
        
        # Check if direct conversion exists
        conversion_key = (from_uom, to_uom)
        if conversion_key in uom_conversions:
            converted_qty = from_qty * uom_conversions[conversion_key]
            return {
                "success": True,
                "original_qty": from_qty,
                "original_uom": from_uom,
                "converted_qty": converted_qty,
                "converted_uom": to_uom,
                "conversion_factor": uom_conversions[conversion_key]
            }
        
        # Check if item-specific UOM conversion exists in ERPNext
        if item_code:
            uom_conversion = frappe.db.get_value("UOM Conversion Detail", {
                "parent": item_code,
                "uom": to_uom
            }, "conversion_factor")
            
            if uom_conversion:
                converted_qty = from_qty * uom_conversion
                return {
                    "success": True,
                    "original_qty": from_qty,
                    "original_uom": from_uom,
                    "converted_qty": converted_qty,
                    "converted_uom": to_uom,
                    "conversion_factor": uom_conversion,
                    "source": "Item UOM Conversion"
                }
        
        # If no conversion found, return error
        return {
            "success": False,
            "message": f"No conversion found from {from_uom} to {to_uom}",
            "available_conversions": list(uom_conversions.keys())
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_uom_conversion_factor(from_uom, to_uom):
    """
    Get conversion factor between two UOMs
    """
    result = convert_uom_quantity(1, from_uom, to_uom)
    if result["success"]:
        return result["conversion_factor"]
    return None


@frappe.whitelist()
def create_bulk_menu_items_from_boms(item_group="Products"):
    """
    Create menu items for all BOMs that don't have corresponding sales items
    """
    try:
        # Get all BOMs that don't have corresponding sales items
        boms_without_sales_items = frappe.db.sql("""
            SELECT b.name, b.item, b.item_name
            FROM `tabBOM` b
            LEFT JOIN `tabItem` i ON b.item = i.item_code AND i.is_sales_item = 1
            WHERE b.is_active = 1 
            AND b.is_default = 1 
            AND b.docstatus = 1
            AND i.item_code IS NULL
        """, as_dict=True)
        
        created_items = []
        errors = []
        
        for bom in boms_without_sales_items:
            result = create_menu_item_from_bom(bom.name, item_group)
            if result["success"]:
                created_items.append(result)
            else:
                errors.append(f"BOM {bom.name}: {result['message']}")
        
        return {
            "success": True,
            "created_count": len(created_items),
            "created_items": created_items,
            "errors": errors,
            "total_boms_processed": len(boms_without_sales_items)
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def validate_bom_ingredients_stock(bom_name, production_qty=1, warehouse=None):
    """
    Validate if sufficient stock is available for all BOM ingredients
    """
    try:
        bom_doc = frappe.get_doc("BOM", bom_name)
        
        if not warehouse:
            # Try to get default warehouse
            warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
        
        validation_results = []
        all_sufficient = True
        
        for item in bom_doc.items:
            required_qty = (item.qty / bom_doc.quantity) * production_qty
            
            # Get available stock
            available_qty = frappe.db.get_value("Bin", {
                "item_code": item.item_code,
                "warehouse": warehouse
            }, "actual_qty") or 0
            
            # Check if UOM conversion is needed
            stock_uom = frappe.db.get_value("Item", item.item_code, "stock_uom")
            if stock_uom != item.uom:
                # Convert required qty to stock UOM
                conversion_result = convert_uom_quantity(required_qty, item.uom, stock_uom, item.item_code)
                if conversion_result["success"]:
                    required_qty_in_stock_uom = conversion_result["converted_qty"]
                else:
                    required_qty_in_stock_uom = required_qty  # Fallback
            else:
                required_qty_in_stock_uom = required_qty
            
            is_sufficient = available_qty >= required_qty_in_stock_uom
            if not is_sufficient:
                all_sufficient = False
            
            validation_results.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "required_qty": required_qty,
                "required_uom": item.uom,
                "required_qty_stock_uom": required_qty_in_stock_uom,
                "stock_uom": stock_uom,
                "available_qty": available_qty,
                "is_sufficient": is_sufficient,
                "shortage": max(0, required_qty_in_stock_uom - available_qty)
            })
        
        return {
            "success": True,
            "bom_name": bom_name,
            "production_qty": production_qty,
            "warehouse": warehouse,
            "all_sufficient": all_sufficient,
            "ingredients": validation_results
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def calculate_food_cost_for_menu_item(item_code, qty=1):
    """
    Calculate food cost for a menu item based on its BOM
    Returns cost breakdown and profit analysis
    """
    try:
        # Get BOM for the item
        bom = frappe.db.get_value("BOM", 
            {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, 
            "name")
        
        if not bom:
            return {"success": False, "message": f"No active BOM found for {item_code}"}
        
        # Use ERPNext's BOM explosion
        from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
        
        bom_items = get_bom_items_as_dict(
            bom=bom,
            company=frappe.defaults.get_user_default("Company"),
            qty=qty,
            fetch_exploded=1
        )
        
        # Calculate total food cost
        total_food_cost = 0
        ingredient_breakdown = []
        
        for item_code_bom, bom_item in bom_items.items():
            ingredient_cost = bom_item.qty * (bom_item.rate or 0)
            total_food_cost += ingredient_cost
            
            ingredient_breakdown.append({
                "item_code": item_code_bom,
                "item_name": bom_item.item_name,
                "qty": bom_item.qty,
                "uom": bom_item.uom,
                "rate": bom_item.rate or 0,
                "cost": ingredient_cost
            })
        
        # Get selling price
        selling_price = frappe.db.get_value("Item Price", 
            {"item_code": item_code}, "price_list_rate") or 0
        
        # Calculate profit
        profit = selling_price - total_food_cost
        profit_percentage = (profit / selling_price * 100) if selling_price > 0 else 0
        food_cost_percentage = (total_food_cost / selling_price * 100) if selling_price > 0 else 0
        
        return {
            "success": True,
            "item_code": item_code,
            "qty": qty,
            "bom_name": bom,
            "total_food_cost": total_food_cost,
            "selling_price": selling_price,
            "profit": profit,
            "profit_percentage": profit_percentage,
            "food_cost_percentage": food_cost_percentage,
            "ingredient_breakdown": ingredient_breakdown
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_pos_invoice_food_cost_analysis(pos_invoice_name):
    """
    Analyze food cost for all items in a POS Invoice
    """
    try:
        pos_invoice = frappe.get_doc("POS Invoice", pos_invoice_name)
        
        total_food_cost = 0
        total_selling_price = 0
        item_analysis = []
        
        for item in pos_invoice.items:
            cost_analysis = calculate_food_cost_for_menu_item(item.item_code, item.qty)
            
            if cost_analysis["success"]:
                total_food_cost += cost_analysis["total_food_cost"]
                total_selling_price += cost_analysis["selling_price"]
                
                item_analysis.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "qty": item.qty,
                    "selling_price": cost_analysis["selling_price"],
                    "food_cost": cost_analysis["total_food_cost"],
                    "profit": cost_analysis["profit"],
                    "profit_percentage": cost_analysis["profit_percentage"]
                })
        
        # Overall analysis
        total_profit = total_selling_price - total_food_cost
        overall_profit_percentage = (total_profit / total_selling_price * 100) if total_selling_price > 0 else 0
        overall_food_cost_percentage = (total_food_cost / total_selling_price * 100) if total_selling_price > 0 else 0
        
        return {
            "success": True,
            "pos_invoice": pos_invoice_name,
            "total_selling_price": total_selling_price,
            "total_food_cost": total_food_cost,
            "total_profit": total_profit,
            "overall_profit_percentage": overall_profit_percentage,
            "overall_food_cost_percentage": overall_food_cost_percentage,
            "item_analysis": item_analysis
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def setup_menu_item_with_bom(item_name, item_group="Menu Items", selling_price=0, ingredients=None):
    """
    Complete setup: Create menu item + BOM + price in one go
    
    ingredients format: [
        {"item_code": "CHICKEN-BREAST", "qty": 150, "uom": "Gram"},
        {"item_code": "BUN", "qty": 1, "uom": "Nos"},
        {"item_code": "OIL", "qty": 10, "uom": "ml"}
    ]
    """
    try:
        if not ingredients:
            return {"success": False, "message": "Ingredients list is required"}
        
        # Parse ingredients if it's a string
        if isinstance(ingredients, str):
            import json
            ingredients = json.loads(ingredients)
        
        # Generate item code from name
        item_code = item_name.upper().replace(" ", "-")
        
        # 1. Create Menu Item
        if not frappe.db.exists("Item", item_code):
            item_doc = frappe.new_doc("Item")
            item_doc.item_code = item_code
            item_doc.item_name = item_name
            item_doc.item_group = item_group
            item_doc.stock_uom = "Nos"  # Default for menu items
            item_doc.is_sales_item = 1
            item_doc.is_stock_item = 0  # Menu items are non-stock
            item_doc.description = f"Menu item: {item_name}"
            item_doc.insert()
        
        # 2. Create BOM
        bom_doc = frappe.new_doc("BOM")
        bom_doc.item = item_code
        bom_doc.item_name = item_name
        bom_doc.quantity = 1  # 1 serving
        bom_doc.uom = "Nos"
        bom_doc.is_active = 1
        bom_doc.is_default = 1
        
        # Add ingredients to BOM
        for ingredient in ingredients:
            bom_doc.append("items", {
                "item_code": ingredient["item_code"],
                "qty": ingredient["qty"],
                "uom": ingredient["uom"],
                "rate": frappe.db.get_value("Item Price", 
                    {"item_code": ingredient["item_code"]}, "price_list_rate") or 0
            })
        
        bom_doc.insert()
        bom_doc.submit()
        
        # 3. Create Item Price
        if selling_price > 0:
            create_item_price(item_code, selling_price)
        
        # 4. Calculate food cost
        cost_analysis = calculate_food_cost_for_menu_item(item_code, 1)
        
        return {
            "success": True,
            "message": f"Menu item {item_name} created successfully",
            "item_code": item_code,
            "bom_name": bom_doc.name,
            "selling_price": selling_price,
            "food_cost_analysis": cost_analysis
        }
        
    except Exception as e:
        frappe.log_error(f"Error setting up menu item {item_name}: {str(e)}", "Menu Item Setup Error")
        return {"success": False, "message": str(e)}