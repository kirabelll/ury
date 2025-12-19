# 🍽️ Restaurant Recipe & Menu Management System

A comprehensive guide to setting up recipe-based inventory management and menu creation in URY Restaurant System.

## 📋 Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Initial Setup](#initial-setup)
4. [Creating Raw Materials](#creating-raw-materials)
5. [Creating Recipes (BOMs)](#creating-recipes-boms)
6. [Creating Menu Items](#creating-menu-items)
7. [Setting Up Inventory Deduction](#setting-up-inventory-deduction)
8. [Dashboard Analytics](#dashboard-analytics)
9. [Examples](#examples)
10. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This system automatically:
- ✅ **Deducts ingredients** from inventory when orders are placed
- ✅ **Calculates food costs** in real-time
- ✅ **Tracks profit margins** for each menu item
- ✅ **Provides inventory alerts** for low stock
- ✅ **Handles UOM conversions** (Liter ↔ ml, Kg ↔ grams, etc.)
- ✅ **Creates comprehensive analytics** and reports

---

## 🔧 System Requirements

- ERPNext v14+ or v15+
- URY Restaurant App installed
- Stock module enabled
- Manufacturing module enabled (for BOMs)

---

## 🚀 Initial Setup

### Step 1: Run Setup Script

```python
# In Frappe console (bench console)
from ury.ury.setup.inventory_setup import setup_complete_dashboard
setup_complete_dashboard()
```

This creates:
- Custom fields for inventory management
- Default item groups
- Restaurant Dashboard workspace

### Step 2: Configure Warehouses

1. Go to **Stock → Warehouse**
2. Create/verify your main warehouse (e.g., "Main Store", "Kitchen Store")
3. Set default warehouse in **Company** settings

### Step 3: Enable Inventory Deduction

1. Go to **POS Profile**
2. Check ✅ **"Enable Inventory Deduction"**
3. Set **Warehouse** (where ingredients are stored)
4. Save

---

## 🥕 Creating Raw Materials (Ingredients)

### Step 1: Create Ingredient Items

1. Go to **Stock → Item → New**
2. Fill details:
   ```
   Item Code: CHICKEN-BREAST
   Item Name: Chicken Breast
   Item Group: Raw Materials
   Stock UOM: Kg
   ✅ Is Stock Item: Yes
   ❌ Is Sales Item: No
   ```

### Step 2: Set Up UOM Conversions

For items that need multiple units (e.g., Kg and grams):

1. In Item → **UOM Conversion Detail**
2. Add conversions:
   ```
   UOM: Gram, Conversion Factor: 0.001
   UOM: Kg, Conversion Factor: 1
   ```

### Step 3: Set Safety Stock Levels

1. In Item → **Reorder Level**
2. Set:
   ```
   Warehouse: Main Store
   Reorder Level: 10 Kg
   Reorder Qty: 50 Kg
   ```

### Example Ingredients List:
```
CHICKEN-BREAST    | Chicken Breast     | Kg    | Raw Materials
BUN               | Burger Bun         | Nos   | Raw Materials  
LETTUCE           | Fresh Lettuce      | Kg    | Raw Materials
TOMATO            | Fresh Tomato       | Kg    | Raw Materials
CHEESE            | Cheese Slice       | Nos   | Raw Materials
OIL               | Cooking Oil        | Liter | Raw Materials
SALT              | Salt               | Kg    | Raw Materials
PEPPER            | Black Pepper       | Kg    | Raw Materials
```

---

## 📝 Creating Recipes (BOMs)

### Method 1: Manual BOM Creation

1. Go to **Manufacturing → BOM → New**
2. Fill details:
   ```
   Item: CHICKEN-BURGER (will be created)
   Item Name: Chicken Burger
   Quantity: 1
   UOM: Nos
   ✅ Is Active: Yes
   ✅ Is Default: Yes
   ```

3. Add **Items** (ingredients):
   ```
   Item Code        | Qty  | UOM   | Rate
   CHICKEN-BREAST   | 0.15 | Kg    | 500
   BUN              | 1    | Nos   | 15
   LETTUCE          | 0.02 | Kg    | 200
   TOMATO           | 0.03 | Kg    | 150
   CHEESE           | 1    | Nos   | 25
   OIL              | 0.01 | Liter | 180
   ```

4. **Submit** the BOM

### Method 2: API-Based Creation

```python
# Create complete menu item with recipe
frappe.call({
    method: "ury.ury.api.inventory_management.setup_menu_item_with_bom",
    args: {
        item_name: "Chicken Burger",
        item_group: "Main Course",
        selling_price: 250,
        ingredients: [
            {"item_code": "CHICKEN-BREAST", "qty": 0.15, "uom": "Kg"},
            {"item_code": "BUN", "qty": 1, "uom": "Nos"},
            {"item_code": "LETTUCE", "qty": 0.02, "uom": "Kg"},
            {"item_code": "TOMATO", "qty": 0.03, "uom": "Kg"},
            {"item_code": "CHEESE", "qty": 1, "uom": "Nos"},
            {"item_code": "OIL", "qty": 0.01, "uom": "Liter"}
        ]
    }
})
```

---

## 🍔 Creating Menu Items

### Method 1: From Existing BOM

```python
# Create menu item from BOM
frappe.call({
    method: "ury.ury.api.inventory_management.create_menu_item_from_bom",
    args: {
        bom_name: "BOM-CHICKEN-BURGER-001",
        item_group: "Main Course",
        selling_price: 250
    }
})
```

### Method 2: Manual Creation

1. Go to **Stock → Item → New**
2. Fill details:
   ```
   Item Code: CHICKEN-BURGER
   Item Name: Chicken Burger
   Item Group: Menu Items
   Stock UOM: Nos
   ❌ Is Stock Item: No
   ✅ Is Sales Item: Yes
   ```

3. Create **Item Price**:
   ```
   Price List: Standard Selling
   Rate: 250
   ```

### Method 3: Bulk Creation

```python
# Create menu items for all BOMs
frappe.call({
    method: "ury.ury.api.inventory_management.create_bulk_menu_items_from_boms",
    args: {item_group: "Menu Items"}
})
```

---

## ⚙️ Setting Up Inventory Deduction

### How It Works

```
Customer Orders → POS Invoice Created
    ↓
System finds BOM for each menu item
    ↓
Calculates ingredient quantities needed
    ↓
Creates Stock Entry (Material Issue)
    ↓
Ingredients automatically deducted from stock
```

### Configuration

1. **POS Profile Settings**:
   - ✅ Enable Inventory Deduction
   - Set Default Warehouse
   - Configure other POS settings

2. **Item Settings**:
   - Ensure all ingredients have stock
   - Set proper UOM conversions
   - Configure safety stock levels

3. **BOM Settings**:
   - Mark as Active and Default
   - Submit all BOMs
   - Verify ingredient quantities

---

## 📊 Dashboard Analytics

### Accessing the Dashboard

1. **Web Dashboard**: `/app/restaurant_dashboard`
2. **ERPNext Report**: Reports → Restaurant Dashboard Summary
3. **Workspace**: Restaurant Dashboard (sidebar)

### Key Metrics Tracked

- 💰 **Sales Revenue** - Total sales amount
- 🍽️ **Food Cost** - Ingredient costs (target: <35%)
- 📈 **Gross Profit** - Sales minus food costs
- 🛒 **Average Order Value** - Revenue per order
- 📦 **Inventory Status** - Stock levels and alerts
- 🏆 **Top Items** - Best selling menu items
- ⚠️ **Stock Alerts** - Low inventory warnings

### Real-time API

```javascript
// Get today's metrics
frappe.call({
    method: 'ury.ury.api.dashboard_analytics.get_realtime_metrics',
    callback: function(r) {
        console.log('Today Sales:', r.message.sales);
        console.log('Food Cost %:', r.message.profit_margin);
    }
});
```

---

## 📚 Complete Examples

### Example 1: Chicken Burger Setup

```python
# 1. Create ingredients (if not exists)
ingredients = [
    {"code": "CHICKEN-BREAST", "name": "Chicken Breast", "uom": "Kg", "rate": 500},
    {"code": "BUN", "name": "Burger Bun", "uom": "Nos", "rate": 15},
    {"code": "LETTUCE", "name": "Fresh Lettuce", "uom": "Kg", "rate": 200},
    {"code": "CHEESE", "name": "Cheese Slice", "uom": "Nos", "rate": 25}
]

# 2. Create complete menu item with recipe
frappe.call({
    method: "ury.ury.api.inventory_management.setup_menu_item_with_bom",
    args: {
        item_name: "Chicken Burger",
        item_group: "Main Course", 
        selling_price: 250,
        ingredients: [
            {"item_code": "CHICKEN-BREAST", "qty": 0.15, "uom": "Kg"},
            {"item_code": "BUN", "qty": 1, "uom": "Nos"},
            {"item_code": "LETTUCE", "qty": 0.02, "uom": "Kg"},
            {"item_code": "CHEESE", "qty": 1, "uom": "Nos"}
        ]
    }
})
```

**Result**: 
- Food Cost: ₹102.50 (0.15×500 + 1×15 + 0.02×200 + 1×25)
- Selling Price: ₹250
- Profit: ₹147.50 (59% margin) ✅

### Example 2: Pizza Margherita

```python
frappe.call({
    method: "ury.ury.api.inventory_management.setup_menu_item_with_bom",
    args: {
        item_name: "Pizza Margherita",
        item_group: "Main Course",
        selling_price: 350,
        ingredients: [
            {"item_code": "PIZZA-DOUGH", "qty": 0.2, "uom": "Kg"},
            {"item_code": "TOMATO-SAUCE", "qty": 0.05, "uom": "Liter"},
            {"item_code": "MOZZARELLA", "qty": 0.1, "uom": "Kg"},
            {"item_code": "BASIL", "qty": 0.005, "uom": "Kg"},
            {"item_code": "OLIVE-OIL", "qty": 0.01, "uom": "Liter"}
        ]
    }
})
```

### Example 3: Checking Food Cost

```python
# Calculate food cost for any menu item
frappe.call({
    method: "ury.ury.api.inventory_management.calculate_food_cost_for_menu_item",
    args: {
        item_code: "CHICKEN-BURGER",
        qty: 1
    },
    callback: function(r) {
        console.log("Food Cost Analysis:", r.message);
        // Shows: ingredient breakdown, total cost, profit margin
    }
})
```

---

## 🔄 UOM Conversion Examples

The system automatically handles conversions:

### Volume Conversions
```
1 Liter = 1000 ml
0.5 Liter = 500 ml
2.5 Liter = 2500 ml
```

### Weight Conversions  
```
1 Kg = 1000 grams
0.15 Kg = 150 grams
2.5 Kg = 2500 grams
```

### Usage in Recipes
```python
# Recipe can use any UOM, system converts automatically
{
    "item_code": "OIL",
    "qty": 10,        # 10 ml needed
    "uom": "ml"       # Recipe specifies ml
}
# System converts to stock UOM (Liter): 10ml = 0.01 Liter
```

---

## 🔍 Troubleshooting

### Issue 1: Ingredients Not Deducting

**Symptoms**: Orders created but no stock entries generated

**Solutions**:
1. ✅ Check POS Profile → "Enable Inventory Deduction" is checked
2. ✅ Verify BOM exists and is Active/Default/Submitted
3. ✅ Ensure ingredients have stock available
4. ✅ Check warehouse is set in POS Profile
5. ✅ Restart server: `bench restart`

### Issue 2: UOM Conversion Errors

**Symptoms**: Wrong quantities deducted

**Solutions**:
1. ✅ Set up UOM conversions in Item master
2. ✅ Use consistent UOMs in BOM and Stock
3. ✅ Check conversion factors are correct

### Issue 3: Food Cost Not Calculating

**Symptoms**: Zero food cost in reports

**Solutions**:
1. ✅ Ensure Stock Entries are submitted
2. ✅ Check item rates are set
3. ✅ Verify custom field "custom_pos_invoice" exists in Stock Entry

### Issue 4: Dashboard Not Loading

**Symptoms**: Dashboard shows errors

**Solutions**:
1. ✅ Run setup script again
2. ✅ Check user permissions for POS Invoice and Stock Entry
3. ✅ Clear cache: `bench clear-cache`

---

## 📞 Support

For issues or questions:

1. **Check Error Log**: Go to Error Log in ERPNext
2. **Console Debugging**: Use browser console for JavaScript errors
3. **Frappe Logs**: Check `bench logs` for server errors

---

## 🎯 Best Practices

### Recipe Management
- ✅ Use descriptive BOM names
- ✅ Keep recipes updated with current costs
- ✅ Regular review of ingredient quantities
- ✅ Test recipes before going live

### Inventory Management  
- ✅ Set appropriate safety stock levels
- ✅ Regular stock reconciliation
- ✅ Monitor food cost percentage (target: 30-35%)
- ✅ Use dashboard alerts proactively

### Menu Optimization
- ✅ Analyze profit margins regularly
- ✅ Promote high-margin items
- ✅ Review low-performing items
- ✅ Adjust prices based on food costs

---

## 🚀 Quick Start Checklist

- [ ] Run setup script
- [ ] Create ingredient items with UOM conversions
- [ ] Add initial stock for ingredients
- [ ] Create BOMs for menu items
- [ ] Create menu items from BOMs
- [ ] Set selling prices
- [ ] Enable inventory deduction in POS Profile
- [ ] Test with sample order
- [ ] Check dashboard analytics
- [ ] Set up stock alerts

**🎉 Your recipe-based inventory management system is now ready!**

---

*Last Updated: December 2024*
*Version: 1.0*