from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum
import json

db = SQLAlchemy()

class Role(Enum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"

class StorageType(Enum):
    FRIDGE = "fridge"
    FREEZER = "freezer"
    PANTRY = "pantry"
    COUNTER = "counter"

class ItemStatus(Enum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    WASTED = "wasted"

class WasteReason(Enum):
    EXPIRED = "expired"
    SPOILED = "spoiled"
    OVERBOUGHT = "overbought"
    FORGOTTEN = "forgotten"
    DAMAGED = "damaged"

class DisposalMethod(Enum):
    TRASH = "trash"
    COMPOST = "compost"
    DONATED = "donated"

class TriggerType(Enum):
    EXPIRY = "expiry"
    LOW_STOCK = "low_stock"
    PRICE_DROP = "price_drop"
    SCHEDULE = "schedule"

class ActionType(Enum):
    NOTIFY = "notify"
    ADD_TO_LIST = "add_to_list"
    SUGGEST_RECIPE = "suggest_recipe"
    MARK_EXPIRED = "mark_expired"

class MealType(Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

# User and Household Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    backup_codes = db.Column(db.Text)
    
    # Relationships
    households = db.relationship('HouseholdMember', back_populates='user')
    inventory_items = db.relationship('Inventory', back_populates='user')
    recipes = db.relationship('Recipe', back_populates='creator')
    meal_plans = db.relationship('MealPlan', back_populates='user')
    grocery_lists = db.relationship('GroceryList', back_populates='user')
    waste_logs = db.relationship('WasteLog', back_populates='user')
    automation_rules = db.relationship('AutomationRule', back_populates='user')
    achievements = db.relationship('Achievement', back_populates='user')
    audit_logs = db.relationship('AuditLog', back_populates='user')

class Household(db.Model):
    __tablename__ = 'households'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship('HouseholdMember', back_populates='household')
    locations = db.relationship('Location', back_populates='household')

class HouseholdMember(db.Model):
    __tablename__ = 'household_members'
    
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('households.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.Enum(Role), default=Role.MEMBER)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    household = db.relationship('Household', back_populates='members')
    user = db.relationship('User', back_populates='households')

# Location and Storage Models
class Location(db.Model):
    __tablename__ = 'locations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum(StorageType), nullable=False)
    household_id = db.Column(db.Integer, db.ForeignKey('households.id'), nullable=False)
    
    # Relationships
    household = db.relationship('Household', back_populates='locations')
    inventory_items = db.relationship('Inventory', back_populates='location')

# Item and Inventory Models
class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    barcode = db.Column(db.String(50), unique=True)
    category = db.Column(db.String(50))
    default_storage = db.Column(db.String(50))
    shelf_life_days = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    inventory_items = db.relationship('Inventory', back_populates='item')
    recipe_ingredients = db.relationship('RecipeIngredient', back_populates='item')
    waste_logs = db.relationship('WasteLog', back_populates='item')

class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit = db.Column(db.String(20), default='units')
    expiry_date = db.Column(db.Date, nullable=False)
    purchase_date = db.Column(db.Date, default=datetime.utcnow)
    price = db.Column(db.Numeric(10, 2))
    notes = db.Column(db.Text)
    status = db.Column(db.Enum(ItemStatus), default=ItemStatus.ACTIVE)
    low_stock_threshold = db.Column(db.Numeric(10, 2), default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='inventory_items')
    item = db.relationship('Item', back_populates='inventory_items')
    location = db.relationship('Location', back_populates='inventory_items')
    waste_logs = db.relationship('WasteLog', back_populates='inventory_item')

# Recipe and Meal Planning Models
class Recipe(db.Model):
    __tablename__ = 'recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    prep_time = db.Column(db.Integer)  # minutes
    cook_time = db.Column(db.Integer)  # minutes
    servings = db.Column(db.Integer)
    calories_per_serving = db.Column(db.Integer)
    allergens = db.Column(db.Text)  # JSON string
    dietary_tags = db.Column(db.Text)  # JSON string
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Numeric(3, 2), default=0)
    rating_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', back_populates='recipes')
    ingredients = db.relationship('RecipeIngredient', back_populates='recipe')
    meal_plans = db.relationship('MealPlan', back_populates='recipe')

class RecipeIngredient(db.Model):
    __tablename__ = 'recipe_ingredients'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    
    # Relationships
    recipe = db.relationship('Recipe', back_populates='ingredients')
    item = db.relationship('Item', back_populates='recipe_ingredients')

class MealPlan(db.Model):
    __tablename__ = 'meal_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    planned_date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.Enum(MealType), nullable=False)
    servings = db.Column(db.Integer, default=1)
    is_completed = db.Column(db.Boolean, default=False)
    
    # Relationships
    user = db.relationship('User', back_populates='meal_plans')
    recipe = db.relationship('Recipe', back_populates='meal_plans')

# Shopping and Budget Models
class GroceryList(db.Model):
    __tablename__ = 'grocery_lists'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), default="My Grocery List")
    total_estimated_cost = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='grocery_lists')
    items = db.relationship('GroceryItem', back_populates='grocery_list')

class GroceryItem(db.Model):
    __tablename__ = 'grocery_items'
    
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('grocery_lists.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    purchased = db.Column(db.Boolean, default=False)
    estimated_price = db.Column(db.Numeric(10, 2))
    actual_price = db.Column(db.Numeric(10, 2))
    store = db.Column(db.String(100))
    
    # Relationships
    grocery_list = db.relationship('GroceryList', back_populates='items')
    item = db.relationship('Item')

class PriceBook(db.Model):
    __tablename__ = 'price_book'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    store = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item')

class Budget(db.Model):
    __tablename__ = 'budgets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    month = db.Column(db.Date, nullable=False)
    total_budget = db.Column(db.Numeric(10, 2), nullable=False)
    spent = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Waste and Sustainability Models
class WasteLog(db.Model):
    __tablename__ = 'waste_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.Enum(WasteReason), nullable=False)
    disposal_method = db.Column(db.Enum(DisposalMethod), nullable=False)
    notes = db.Column(db.Text)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='waste_logs')
    item = db.relationship('Item', back_populates='waste_logs')
    inventory_item = db.relationship('Inventory', back_populates='waste_logs')

class SustainabilityScore(db.Model):
    __tablename__ = 'sustainability_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    month = db.Column(db.Date, nullable=False)
    co2_saved = db.Column(db.Numeric(10, 2), default=0)
    water_saved = db.Column(db.Numeric(10, 2), default=0)
    waste_reduced = db.Column(db.Numeric(10, 2), default=0)
    score = db.Column(db.Integer, default=0)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)

# Automation and Rules Models
class AutomationRule(db.Model):
    __tablename__ = 'automation_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    trigger_type = db.Column(db.Enum(TriggerType), nullable=False)
    trigger_conditions = db.Column(db.Text)  # JSON string
    action_type = db.Column(db.Enum(ActionType), nullable=False)
    action_config = db.Column(db.Text)  # JSON string
    is_active = db.Column(db.Boolean, default=True)
    last_triggered = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='automation_rules')

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    action_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Community and Achievement Models
class Achievement(db.Model):
    __tablename__ = 'achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    achievement_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    points = db.Column(db.Integer, default=0)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='achievements')

class CommunityRecipe(db.Model):
    __tablename__ = 'community_recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    shared_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    likes = db.Column(db.Integer, default=0)
    shares = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    recipe = db.relationship('Recipe')
    user = db.relationship('User')

class Challenge(db.Model):
    __tablename__ = 'challenges'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reward_points = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Security and Audit Models
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer)
    changes = db.Column(db.Text)  # JSON string
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='audit_logs')

class DeviceSession(db.Model):
    __tablename__ = 'device_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    device_name = db.Column(db.String(255))
    device_type = db.Column(db.String(50))
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
