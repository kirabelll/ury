"""
Restaurant Dashboard Summary Report
Provides key metrics and analytics for restaurant operations
"""

import frappe
from frappe import _
from frappe.utils import getdate, today, add_days, flt

def execute(filters=None):
    if not filters:
        filters = {}
    
    # Set default date range
    if not filters.get("from_date"):
        filters["from_date"] = today()
    if not filters.get("to_date"):
        filters["to_date"] = today()
    
    columns = get_columns()
    data = get_data(filters)
    charts = get_charts(filters)
    
    return columns, data, None, charts

def get_columns():
    return [
        {
            "fieldname": "metric",
            "label": _("Metric"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "value",
            "label": _("Value"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "percentage",
            "label": _("Percentage"),
            "fieldtype": "Percent",
            "width": 100
        },
        {
            "fieldname": "description",
            "label": _("Description"),
            "fieldtype": "Data",
            "width": 300
        }
    ]

def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    # Get sales summary
    sales_data = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_orders,
            SUM(grand_total) as total_sales,
            SUM(net_total) as net_sales,
            AVG(grand_total) as avg_order_value
        FROM `tabPOS Invoice`
        WHERE posting_date BETWEEN %s AND %s
        AND docstatus = 1
    """, (from_date, to_date), as_dict=True)[0]
    
    # Get food cost
    food_cost_data = frappe.db.sql("""
        SELECT SUM(sei.amount) as total_food_cost
        FROM `tabStock Entry` se
        INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
        WHERE se.posting_date BETWEEN %s AND %s
        AND se.stock_entry_type = 'Material Issue'
        AND se.custom_pos_invoice IS NOT NULL
        AND se.docstatus = 1
    """, (from_date, to_date), as_dict=True)[0]
    
    total_sales = sales_data.total_sales or 0
    total_food_cost = food_cost_data.total_food_cost or 0
    gross_profit = total_sales - total_food_cost
    
    # Calculate percentages
    food_cost_pct = (total_food_cost / total_sales * 100) if total_sales > 0 else 0
    profit_margin_pct = (gross_profit / total_sales * 100) if total_sales > 0 else 0
    
    data = [
        {
            "metric": "📊 Total Orders",
            "value": sales_data.total_orders or 0,
            "percentage": 0,
            "description": f"Orders from {from_date} to {to_date}"
        },
        {
            "metric": "💰 Total Sales",
            "value": total_sales,
            "percentage": 100,
            "description": "Gross revenue from all orders"
        },
        {
            "metric": "🍽️ Food Cost",
            "value": total_food_cost,
            "percentage": food_cost_pct,
            "description": "Cost of ingredients consumed"
        },
        {
            "metric": "📈 Gross Profit",
            "value": gross_profit,
            "percentage": profit_margin_pct,
            "description": "Sales minus food costs"
        },
        {
            "metric": "🛒 Average Order Value",
            "value": sales_data.avg_order_value or 0,
            "percentage": 0,
            "description": "Average amount per order"
        }
    ]
    
    # Add inventory metrics
    inventory_data = frappe.db.sql("""
        SELECT 
            SUM(b.stock_value) as total_inventory_value,
            COUNT(CASE WHEN b.actual_qty <= COALESCE(i.safety_stock, 10) THEN 1 END) as low_stock_items
        FROM `tabBin` b
        INNER JOIN `tabItem` i ON b.item_code = i.item_code
        WHERE i.is_stock_item = 1
        AND b.actual_qty >= 0
    """, as_dict=True)[0]
    
    data.extend([
        {
            "metric": "📦 Inventory Value",
            "value": inventory_data.total_inventory_value or 0,
            "percentage": 0,
            "description": "Total value of current stock"
        },
        {
            "metric": "⚠️ Low Stock Items",
            "value": inventory_data.low_stock_items or 0,
            "percentage": 0,
            "description": "Items below safety stock level"
        }
    ])
    
    return data

def get_charts(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    # Daily sales trend
    daily_data = frappe.db.sql("""
        SELECT 
            posting_date,
            SUM(grand_total) as sales,
            COUNT(*) as orders
        FROM `tabPOS Invoice`
        WHERE posting_date BETWEEN %s AND %s
        AND docstatus = 1
        GROUP BY posting_date
        ORDER BY posting_date
    """, (from_date, to_date), as_dict=True)
    
    # Top selling items
    top_items = frappe.db.sql("""
        SELECT 
            pii.item_name,
            SUM(pii.qty) as total_qty,
            SUM(pii.amount) as total_sales
        FROM `tabPOS Invoice` pi
        INNER JOIN `tabPOS Invoice Item` pii ON pi.name = pii.parent
        WHERE pi.posting_date BETWEEN %s AND %s
        AND pi.docstatus = 1
        GROUP BY pii.item_code
        ORDER BY total_qty DESC
        LIMIT 10
    """, (from_date, to_date), as_dict=True)
    
    charts = [
        {
            "name": "Daily Sales Trend",
            "chart_name": _("Daily Sales Trend"),
            "chart_type": "line",
            "data": {
                "labels": [d.posting_date.strftime("%m/%d") for d in daily_data],
                "datasets": [
                    {
                        "name": "Sales",
                        "values": [d.sales for d in daily_data]
                    },
                    {
                        "name": "Orders",
                        "values": [d.orders for d in daily_data]
                    }
                ]
            }
        },
        {
            "name": "Top Selling Items",
            "chart_name": _("Top Selling Items"),
            "chart_type": "bar",
            "data": {
                "labels": [item.item_name[:20] for item in top_items],
                "datasets": [
                    {
                        "name": "Quantity Sold",
                        "values": [item.total_qty for item in top_items]
                    }
                ]
            }
        }
    ]
    
    return charts