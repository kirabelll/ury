"""
Restaurant Dashboard Analytics API
Provides comprehensive analytics for inventory, food costs, and profitability
"""

import frappe
from frappe import _
from frappe.utils import today, add_days, getdate, flt
from datetime import datetime, timedelta
import json

@frappe.whitelist()
def get_dashboard_overview(date_range="Today"):
    """
    Get comprehensive dashboard overview
    """
    try:
        # Get date range
        from_date, to_date = get_date_range(date_range)
        
        # Get all analytics
        sales_summary = get_sales_summary(from_date, to_date)
        food_cost_analysis = get_food_cost_analysis(from_date, to_date)
        inventory_status = get_inventory_status()
        top_items = get_top_selling_items(from_date, to_date)
        profit_analysis = get_profit_analysis(from_date, to_date)
        stock_alerts = get_stock_alerts()
        
        return {
            "success": True,
            "date_range": {"from": from_date, "to": to_date, "label": date_range},
            "sales_summary": sales_summary,
            "food_cost_analysis": food_cost_analysis,
            "inventory_status": inventory_status,
            "top_items": top_items,
            "profit_analysis": profit_analysis,
            "stock_alerts": stock_alerts
        }
        
    except Exception as e:
        frappe.log_error(f"Dashboard overview error: {str(e)}", "Dashboard Error")
        return {"success": False, "message": str(e)}


def get_date_range(range_type):
    """Get from_date and to_date based on range type"""
    today_date = getdate(today())
    
    if range_type == "Today":
        return today_date, today_date
    elif range_type == "Yesterday":
        yesterday = add_days(today_date, -1)
        return yesterday, yesterday
    elif range_type == "This Week":
        from_date = add_days(today_date, -today_date.weekday())
        return from_date, today_date
    elif range_type == "Last Week":
        from_date = add_days(today_date, -today_date.weekday() - 7)
        to_date = add_days(from_date, 6)
        return from_date, to_date
    elif range_type == "This Month":
        from_date = today_date.replace(day=1)
        return from_date, today_date
    elif range_type == "Last Month":
        last_month = add_days(today_date.replace(day=1), -1)
        from_date = last_month.replace(day=1)
        return from_date, last_month
    else:
        return today_date, today_date


@frappe.whitelist()
def get_sales_summary(from_date=None, to_date=None):
    """Get sales summary with food cost breakdown"""
    try:
        if not from_date:
            from_date = today()
        if not to_date:
            to_date = today()
        
        # Get POS Invoice summary
        sales_data = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_orders,
                SUM(grand_total) as total_sales,
                SUM(net_total) as net_sales,
                SUM(total_taxes_and_charges) as total_taxes,
                AVG(grand_total) as avg_order_value,
                COUNT(DISTINCT customer) as unique_customers
            FROM `tabPOS Invoice`
            WHERE posting_date BETWEEN %s AND %s
            AND docstatus = 1
        """, (from_date, to_date), as_dict=True)[0]
        
        # Get food cost from stock entries
        food_cost_data = frappe.db.sql("""
            SELECT 
                SUM(sei.amount) as total_food_cost
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
            WHERE se.posting_date BETWEEN %s AND %s
            AND se.stock_entry_type = 'Material Issue'
            AND se.custom_pos_invoice IS NOT NULL
            AND se.docstatus = 1
        """, (from_date, to_date), as_dict=True)[0]
        
        total_food_cost = food_cost_data.total_food_cost or 0
        total_sales = sales_data.total_sales or 0
        
        # Calculate metrics
        gross_profit = total_sales - total_food_cost
        food_cost_percentage = (total_food_cost / total_sales * 100) if total_sales > 0 else 0
        profit_margin = (gross_profit / total_sales * 100) if total_sales > 0 else 0
        
        return {
            "total_orders": sales_data.total_orders or 0,
            "total_sales": total_sales,
            "total_food_cost": total_food_cost,
            "gross_profit": gross_profit,
            "food_cost_percentage": round(food_cost_percentage, 2),
            "profit_margin": round(profit_margin, 2),
            "avg_order_value": round(sales_data.avg_order_value or 0, 2),
            "unique_customers": sales_data.unique_customers or 0
        }
        
    except Exception as e:
        frappe.log_error(f"Sales summary error: {str(e)}", "Dashboard Error")
        return {}


@frappe.whitelist()
def get_food_cost_analysis(from_date=None, to_date=None):
    """Get detailed food cost analysis"""
    try:
        if not from_date:
            from_date = today()
        if not to_date:
            to_date = today()
        
        # Get food cost by category
        category_costs = frappe.db.sql("""
            SELECT 
                ig.item_group_name as category,
                SUM(sei.amount) as cost,
                SUM(sei.qty) as qty_consumed
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
            INNER JOIN `tabItem` i ON sei.item_code = i.item_code
            INNER JOIN `tabItem Group` ig ON i.item_group = ig.name
            WHERE se.posting_date BETWEEN %s AND %s
            AND se.stock_entry_type = 'Material Issue'
            AND se.custom_pos_invoice IS NOT NULL
            AND se.docstatus = 1
            GROUP BY ig.item_group_name
            ORDER BY cost DESC
            LIMIT 10
        """, (from_date, to_date), as_dict=True)
        
        # Get top cost ingredients
        top_ingredients = frappe.db.sql("""
            SELECT 
                sei.item_code,
                sei.item_name,
                SUM(sei.amount) as total_cost,
                SUM(sei.qty) as total_qty,
                sei.uom,
                COUNT(DISTINCT se.custom_pos_invoice) as orders_count
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
            WHERE se.posting_date BETWEEN %s AND %s
            AND se.stock_entry_type = 'Material Issue'
            AND se.custom_pos_invoice IS NOT NULL
            AND se.docstatus = 1
            GROUP BY sei.item_code
            ORDER BY total_cost DESC
            LIMIT 10
        """, (from_date, to_date), as_dict=True)
        
        return {
            "category_breakdown": category_costs,
            "top_ingredients": top_ingredients
        }
        
    except Exception as e:
        frappe.log_error(f"Food cost analysis error: {str(e)}", "Dashboard Error")
        return {"category_breakdown": [], "top_ingredients": []}


@frappe.whitelist()
def get_inventory_status():
    """Get current inventory status and alerts"""
    try:
        # Get low stock items
        low_stock_items = frappe.db.sql("""
            SELECT 
                b.item_code,
                i.item_name,
                b.actual_qty,
                i.stock_uom,
                COALESCE(i.safety_stock, 0) as safety_stock,
                b.warehouse
            FROM `tabBin` b
            INNER JOIN `tabItem` i ON b.item_code = i.item_code
            WHERE b.actual_qty <= COALESCE(i.safety_stock, 10)
            AND i.is_stock_item = 1
            AND b.actual_qty >= 0
            ORDER BY b.actual_qty ASC
            LIMIT 20
        """, as_dict=True)
        
        # Get total inventory value
        inventory_value = frappe.db.sql("""
            SELECT 
                SUM(b.stock_value) as total_value,
                COUNT(DISTINCT b.item_code) as total_items,
                COUNT(DISTINCT b.warehouse) as total_warehouses
            FROM `tabBin` b
            INNER JOIN `tabItem` i ON b.item_code = i.item_code
            WHERE i.is_stock_item = 1
            AND b.actual_qty > 0
        """, as_dict=True)[0]
        
        # Get fast moving items (high consumption)
        fast_moving = frappe.db.sql("""
            SELECT 
                sei.item_code,
                sei.item_name,
                SUM(sei.qty) as total_consumed,
                sei.uom,
                COUNT(DISTINCT se.custom_pos_invoice) as frequency
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
            WHERE se.posting_date >= %s
            AND se.stock_entry_type = 'Material Issue'
            AND se.custom_pos_invoice IS NOT NULL
            AND se.docstatus = 1
            GROUP BY sei.item_code
            ORDER BY total_consumed DESC
            LIMIT 10
        """, (add_days(today(), -30),), as_dict=True)
        
        return {
            "low_stock_items": low_stock_items,
            "inventory_summary": {
                "total_value": inventory_value.total_value or 0,
                "total_items": inventory_value.total_items or 0,
                "total_warehouses": inventory_value.total_warehouses or 0,
                "low_stock_count": len(low_stock_items)
            },
            "fast_moving_items": fast_moving
        }
        
    except Exception as e:
        frappe.log_error(f"Inventory status error: {str(e)}", "Dashboard Error")
        return {}


@frappe.whitelist()
def get_top_selling_items(from_date=None, to_date=None, limit=10):
    """Get top selling menu items with profitability"""
    try:
        if not from_date:
            from_date = today()
        if not to_date:
            to_date = today()
        
        top_items = frappe.db.sql("""
            SELECT 
                pii.item_code,
                pii.item_name,
                SUM(pii.qty) as total_qty,
                SUM(pii.amount) as total_sales,
                AVG(pii.rate) as avg_price,
                COUNT(DISTINCT pi.name) as order_count
            FROM `tabPOS Invoice` pi
            INNER JOIN `tabPOS Invoice Item` pii ON pi.name = pii.parent
            WHERE pi.posting_date BETWEEN %s AND %s
            AND pi.docstatus = 1
            GROUP BY pii.item_code
            ORDER BY total_qty DESC
            LIMIT %s
        """, (from_date, to_date, limit), as_dict=True)
        
        # Calculate food cost for each item
        for item in top_items:
            # Get food cost from stock entries
            food_cost = frappe.db.sql("""
                SELECT SUM(sei.amount) as cost
                FROM `tabStock Entry` se
                INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
                INNER JOIN `tabPOS Invoice Item` pii ON se.custom_pos_invoice = pii.parent
                WHERE pii.item_code = %s
                AND se.posting_date BETWEEN %s AND %s
                AND se.stock_entry_type = 'Material Issue'
                AND se.docstatus = 1
            """, (item.item_code, from_date, to_date), as_dict=True)[0]
            
            item_food_cost = food_cost.cost or 0
            item["food_cost"] = item_food_cost
            item["profit"] = item.total_sales - item_food_cost
            item["profit_margin"] = (item.profit / item.total_sales * 100) if item.total_sales > 0 else 0
        
        return top_items
        
    except Exception as e:
        frappe.log_error(f"Top selling items error: {str(e)}", "Dashboard Error")
        return []


@frappe.whitelist()
def get_profit_analysis(from_date=None, to_date=None):
    """Get detailed profit analysis"""
    try:
        if not from_date:
            from_date = today()
        if not to_date:
            to_date = today()
        
        # Daily profit trend
        daily_profit = frappe.db.sql("""
            SELECT 
                pi.posting_date,
                SUM(pi.grand_total) as sales,
                COALESCE(se_summary.food_cost, 0) as food_cost,
                (SUM(pi.grand_total) - COALESCE(se_summary.food_cost, 0)) as profit
            FROM `tabPOS Invoice` pi
            LEFT JOIN (
                SELECT 
                    DATE(se.posting_date) as posting_date,
                    SUM(sei.amount) as food_cost
                FROM `tabStock Entry` se
                INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
                WHERE se.stock_entry_type = 'Material Issue'
                AND se.custom_pos_invoice IS NOT NULL
                AND se.docstatus = 1
                GROUP BY DATE(se.posting_date)
            ) se_summary ON pi.posting_date = se_summary.posting_date
            WHERE pi.posting_date BETWEEN %s AND %s
            AND pi.docstatus = 1
            GROUP BY pi.posting_date
            ORDER BY pi.posting_date
        """, (from_date, to_date), as_dict=True)
        
        # Profit by order type
        profit_by_type = frappe.db.sql("""
            SELECT 
                pi.order_type,
                COUNT(*) as order_count,
                SUM(pi.grand_total) as total_sales,
                AVG(pi.grand_total) as avg_order_value
            FROM `tabPOS Invoice` pi
            WHERE pi.posting_date BETWEEN %s AND %s
            AND pi.docstatus = 1
            GROUP BY pi.order_type
            ORDER BY total_sales DESC
        """, (from_date, to_date), as_dict=True)
        
        return {
            "daily_trend": daily_profit,
            "by_order_type": profit_by_type
        }
        
    except Exception as e:
        frappe.log_error(f"Profit analysis error: {str(e)}", "Dashboard Error")
        return {"daily_trend": [], "by_order_type": []}


@frappe.whitelist()
def get_stock_alerts():
    """Get stock alerts and recommendations"""
    try:
        alerts = []
        
        # Low stock alerts
        low_stock = frappe.db.sql("""
            SELECT 
                b.item_code,
                i.item_name,
                b.actual_qty,
                i.stock_uom,
                COALESCE(i.safety_stock, 0) as safety_stock
            FROM `tabBin` b
            INNER JOIN `tabItem` i ON b.item_code = i.item_code
            WHERE b.actual_qty <= COALESCE(i.safety_stock, 5)
            AND i.is_stock_item = 1
            AND b.actual_qty >= 0
            ORDER BY b.actual_qty ASC
            LIMIT 10
        """, as_dict=True)
        
        for item in low_stock:
            alerts.append({
                "type": "low_stock",
                "severity": "high" if item.actual_qty <= item.safety_stock / 2 else "medium",
                "message": f"Low stock: {item.item_name} ({item.actual_qty} {item.stock_uom} remaining)",
                "item_code": item.item_code,
                "current_qty": item.actual_qty,
                "safety_stock": item.safety_stock
            })
        
        # High food cost items
        high_cost_items = frappe.db.sql("""
            SELECT 
                pii.item_code,
                pii.item_name,
                AVG(pii.rate) as avg_selling_price,
                food_costs.avg_food_cost,
                ((AVG(pii.rate) - food_costs.avg_food_cost) / AVG(pii.rate) * 100) as profit_margin
            FROM `tabPOS Invoice Item` pii
            INNER JOIN `tabPOS Invoice` pi ON pii.parent = pi.name
            INNER JOIN (
                SELECT 
                    pii2.item_code,
                    AVG(sei.amount / pii2.qty) as avg_food_cost
                FROM `tabStock Entry` se
                INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
                INNER JOIN `tabPOS Invoice Item` pii2 ON se.custom_pos_invoice = pii2.parent
                WHERE se.stock_entry_type = 'Material Issue'
                AND se.docstatus = 1
                GROUP BY pii2.item_code
            ) food_costs ON pii.item_code = food_costs.item_code
            WHERE pi.posting_date >= %s
            AND pi.docstatus = 1
            GROUP BY pii.item_code
            HAVING profit_margin < 30
            ORDER BY profit_margin ASC
            LIMIT 5
        """, (add_days(today(), -7),), as_dict=True)
        
        for item in high_cost_items:
            alerts.append({
                "type": "low_profit",
                "severity": "medium",
                "message": f"Low profit margin: {item.item_name} ({item.profit_margin:.1f}% margin)",
                "item_code": item.item_code,
                "profit_margin": item.profit_margin,
                "avg_selling_price": item.avg_selling_price,
                "avg_food_cost": item.avg_food_cost
            })
        
        return alerts
        
    except Exception as e:
        frappe.log_error(f"Stock alerts error: {str(e)}", "Dashboard Error")
        return []


@frappe.whitelist()
def get_menu_performance_analysis(from_date=None, to_date=None):
    """Analyze menu item performance with recommendations"""
    try:
        if not from_date:
            from_date = add_days(today(), -30)
        if not to_date:
            to_date = today()
        
        menu_analysis = frappe.db.sql("""
            SELECT 
                pii.item_code,
                pii.item_name,
                SUM(pii.qty) as total_sold,
                SUM(pii.amount) as total_revenue,
                AVG(pii.rate) as avg_price,
                COUNT(DISTINCT pi.name) as order_frequency,
                COUNT(DISTINCT pi.customer) as unique_customers
            FROM `tabPOS Invoice Item` pii
            INNER JOIN `tabPOS Invoice` pi ON pii.parent = pi.name
            WHERE pi.posting_date BETWEEN %s AND %s
            AND pi.docstatus = 1
            GROUP BY pii.item_code
            ORDER BY total_sold DESC
        """, (from_date, to_date), as_dict=True)
        
        # Categorize items
        total_items = len(menu_analysis)
        if total_items == 0:
            return {"categories": {}, "recommendations": []}
        
        # Calculate percentiles
        sorted_by_sales = sorted(menu_analysis, key=lambda x: x.total_sold, reverse=True)
        sorted_by_profit = sorted(menu_analysis, key=lambda x: x.total_revenue, reverse=True)
        
        categories = {
            "stars": [],      # High sales, high profit
            "plowhorses": [], # High sales, low profit  
            "puzzles": [],    # Low sales, high profit
            "dogs": []        # Low sales, low profit
        }
        
        recommendations = []
        
        for i, item in enumerate(menu_analysis):
            sales_rank = next(j for j, x in enumerate(sorted_by_sales) if x.item_code == item.item_code)
            profit_rank = next(j for j, x in enumerate(sorted_by_profit) if x.item_code == item.item_code)
            
            high_sales = sales_rank < total_items * 0.3
            high_profit = profit_rank < total_items * 0.3
            
            if high_sales and high_profit:
                categories["stars"].append(item)
            elif high_sales and not high_profit:
                categories["plowhorses"].append(item)
                recommendations.append({
                    "item": item.item_name,
                    "type": "cost_optimization",
                    "message": f"High sales but low profit. Consider reducing food costs or increasing price."
                })
            elif not high_sales and high_profit:
                categories["puzzles"].append(item)
                recommendations.append({
                    "item": item.item_name,
                    "type": "promotion",
                    "message": f"High profit margin but low sales. Consider promoting this item."
                })
            else:
                categories["dogs"].append(item)
                recommendations.append({
                    "item": item.item_name,
                    "type": "review",
                    "message": f"Low sales and profit. Consider removing or redesigning this item."
                })
        
        return {
            "categories": categories,
            "recommendations": recommendations,
            "analysis_period": {"from": from_date, "to": to_date}
        }
        
    except Exception as e:
        frappe.log_error(f"Menu performance analysis error: {str(e)}", "Dashboard Error")
        return {"categories": {}, "recommendations": []}
@frappe.whitelist()
def get_realtime_metrics():
    """Get real-time metrics for today - lightweight version"""
    try:
        today_date = today()
        
        # Today's sales
        today_sales = frappe.db.sql("""
            SELECT 
                COUNT(*) as orders,
                COALESCE(SUM(grand_total), 0) as sales,
                COALESCE(AVG(grand_total), 0) as avg_order
            FROM `tabPOS Invoice`
            WHERE posting_date = %s AND docstatus = 1
        """, (today_date,), as_dict=True)[0]
        
        # Today's food cost
        today_food_cost = frappe.db.sql("""
            SELECT COALESCE(SUM(sei.amount), 0) as food_cost
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
            WHERE se.posting_date = %s
            AND se.stock_entry_type = 'Material Issue'
            AND se.custom_pos_invoice IS NOT NULL
            AND se.docstatus = 1
        """, (today_date,), as_dict=True)[0]
        
        # Low stock count
        low_stock_count = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabBin` b
            INNER JOIN `tabItem` i ON b.item_code = i.item_code
            WHERE b.actual_qty <= COALESCE(i.safety_stock, 10)
            AND i.is_stock_item = 1
            AND b.actual_qty >= 0
        """, as_dict=True)[0]
        
        sales_amount = today_sales.sales
        food_cost_amount = today_food_cost.food_cost
        profit = sales_amount - food_cost_amount
        profit_margin = (profit / sales_amount * 100) if sales_amount > 0 else 0
        
        return {
            "success": True,
            "date": today_date,
            "orders": today_sales.orders,
            "sales": sales_amount,
            "food_cost": food_cost_amount,
            "profit": profit,
            "profit_margin": round(profit_margin, 1),
            "avg_order_value": round(today_sales.avg_order, 2),
            "low_stock_items": low_stock_count.count
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_quick_alerts():
    """Get quick alerts for immediate attention"""
    try:
        alerts = []
        
        # Critical low stock (less than 5 units)
        critical_stock = frappe.db.sql("""
            SELECT i.item_name, b.actual_qty, i.stock_uom
            FROM `tabBin` b
            INNER JOIN `tabItem` i ON b.item_code = i.item_code
            WHERE b.actual_qty <= 5
            AND i.is_stock_item = 1
            AND b.actual_qty >= 0
            ORDER BY b.actual_qty ASC
            LIMIT 5
        """, as_dict=True)
        
        for item in critical_stock:
            alerts.append({
                "type": "critical_stock",
                "message": f"CRITICAL: {item.item_name} only {item.actual_qty} {item.stock_uom} left!",
                "severity": "high"
            })
        
        # High food cost today (over 40%)
        today_metrics = get_realtime_metrics()
        if today_metrics["success"] and today_metrics["sales"] > 0:
            food_cost_pct = (today_metrics["food_cost"] / today_metrics["sales"]) * 100
            if food_cost_pct > 40:
                alerts.append({
                    "type": "high_food_cost",
                    "message": f"High food cost today: {food_cost_pct:.1f}% (Target: <35%)",
                    "severity": "medium"
                })
        
        return {"success": True, "alerts": alerts}
        
    except Exception as e:
        return {"success": False, "message": str(e)}