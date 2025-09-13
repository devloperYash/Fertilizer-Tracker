from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, DecimalField, SubmitField, SelectField, PasswordField, TextAreaField, IntegerField, FloatField
from wtforms.validators import DataRequired, NumberRange, Email, Length, EqualTo, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from collections import Counter
import os
import csv
import io
from datetime import datetime, date
from sqlalchemy import text
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fertilizer_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your fertilizer data.'
login_manager.login_message_category = 'info'

# User Model for Authentication
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    farm_name = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    is_user_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with bills
    bills = db.relationship('Bill', backref='owner', lazy=True, cascade='all, delete-orphan')
    
    # Enhanced relationships for comprehensive expense management
    expenses = db.relationship('Expense', backref='owner', lazy=True, cascade='all, delete-orphan')
    suppliers = db.relationship('Supplier', backref='owner', lazy=True, cascade='all, delete-orphan')
    fields = db.relationship('Field', backref='owner', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Check if user is admin (yashlawankar@gmail.com)"""
        return self.email == 'yashlawankar@gmail.com'
    
    def __repr__(self):
        return f'<User {self.name}: {self.email}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin helper functions
def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def active_user_required(f):
    """Decorator to require active user status"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and not current_user.is_user_active:
            logout_user()
            flash('Your account has been deactivated. Please contact the administrator.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Bill Model for grouping fertilizers
class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(50), nullable=True)
    purchase_date = db.Column(db.Date, nullable=False, default=date.today)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with fertilizers
    fertilizers = db.relationship('Fertilizer', backref='bill', lazy=True, cascade='all, delete-orphan')
    
    @property
    def fertilizer_count(self):
        try:
            return len(list(self.fertilizers))
        except:
            return 0
    
    def calculate_total(self):
        """Calculate total amount from fertilizers"""
        try:
            self.total_amount = sum(f.price for f in list(self.fertilizers))
        except:
            self.total_amount = 0.0
        return self.total_amount
    
    def __repr__(self):
        return f'<Bill {self.bill_number or self.id}: ₹{self.total_amount} ({self.fertilizer_count} items)>'

# Fertilizer Model (Updated to relate to Bill)
class Fertilizer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='Urea')
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Fertilizer {self.name}: ₹{self.price}>'

# Enhanced Expense Management Models

class ExpenseCategory(db.Model):
    """Categories for different types of farm expenses"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), default='fas fa-tag')
    color = db.Column(db.String(20), default='primary')
    requires_quantity = db.Column(db.Boolean, default=True)
    default_unit = db.Column(db.String(20), default='kg')
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    expenses = db.relationship('Expense', backref='category_ref', lazy=True)
    
    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'

class Supplier(db.Model):
    """Supplier/Vendor information"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(15), nullable=True)
    address = db.Column(db.Text, nullable=True)
    credit_terms = db.Column(db.String(100), nullable=True)  # e.g., "30 days", "Cash only"
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    expenses = db.relationship('Expense', backref='supplier_ref', lazy=True)
    
    def __repr__(self):
        return f'<Supplier {self.name}>'

class Field(db.Model):
    """Field/Plot information for associating expenses with specific land areas"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    area_acres = db.Column(db.Float, nullable=True)
    location = db.Column(db.String(200), nullable=True)
    soil_type = db.Column(db.String(50), nullable=True)
    crop_cycle = db.Column(db.String(100), nullable=True)  # Current crop
    season = db.Column(db.String(50), nullable=True)  # Kharif, Rabi, Zaid
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    expenses = db.relationship('Expense', backref='field_ref', lazy=True)
    
    def __repr__(self):
        return f'<Field {self.name}: {self.area_acres} acres>'

class Expense(db.Model):
    """Comprehensive expense tracking with quantities, suppliers, and field association"""
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # For compatibility
    
    # Quantity and pricing
    quantity = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(20), nullable=True)  # kg, liters, bags, hours, days, acres
    unit_price = db.Column(db.Float, nullable=True)
    total_amount = db.Column(db.Float, nullable=False)
    
    # Relationships
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    field_id = db.Column(db.Integer, db.ForeignKey('field.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Date and payment info
    expense_date = db.Column(db.Date, nullable=False, default=date.today)
    payment_method = db.Column(db.String(50), default='Cash')  # Cash, Credit, Bank Transfer, UPI
    payment_status = db.Column(db.String(50), default='Paid')  # Paid, Pending, Partial
    
    # Additional information
    season = db.Column(db.String(50), nullable=True)  # Kharif, Rabi, Zaid
    crop_cycle = db.Column(db.String(100), nullable=True)
    application_date = db.Column(db.Date, nullable=True)  # For fertilizers/pesticides
    notes = db.Column(db.Text, nullable=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def per_unit_display(self):
        """Display unit cost if applicable"""
        if self.unit_price and self.unit:
            return f"₹{self.unit_price:.2f}/{self.unit}"
        return ""
    
    @property
    def quantity_display(self):
        """Display quantity with unit"""
        if self.quantity and self.unit:
            return f"{self.quantity} {self.unit}"
        return ""
    
    def __repr__(self):
        return f'<Expense {self.description}: ₹{self.total_amount}>'

# Comprehensive Indian Farming Expense Categories
COMPREHENSIVE_EXPENSE_CATEGORIES = [
    # Fertilizers & Nutrients
    {
        'name': 'fertilizers',
        'display_name': 'Fertilizers & Nutrients',
        'icon': 'fas fa-seedling',
        'color': 'success',
        'requires_quantity': True,
        'default_unit': 'kg',
        'description': 'All types of fertilizers including Urea, DAP, NPK, organic fertilizers'
    },
    # Seeds & Planting Material
    {
        'name': 'seeds',
        'display_name': 'Seeds & Planting Material',
        'icon': 'fas fa-spa',
        'color': 'primary',
        'requires_quantity': True,
        'default_unit': 'kg',
        'description': 'Seeds, seedlings, saplings, bulbs for planting'
    },
    # Labor & Wages
    {
        'name': 'labor',
        'display_name': 'Labor & Wages',
        'icon': 'fas fa-users',
        'color': 'warning',
        'requires_quantity': True,
        'default_unit': 'days',
        'description': 'Worker wages, labor charges, contracted services'
    },
    # Equipment & Machinery
    {
        'name': 'equipment',
        'display_name': 'Equipment & Machinery',
        'icon': 'fas fa-cogs',
        'color': 'info',
        'requires_quantity': False,
        'default_unit': 'units',
        'description': 'Farm equipment, machinery purchase/rental, maintenance'
    },
    # Crop Protection
    {
        'name': 'crop_protection',
        'display_name': 'Crop Protection',
        'icon': 'fas fa-shield-virus',
        'color': 'danger',
        'requires_quantity': True,
        'default_unit': 'liters',
        'description': 'Pesticides, insecticides, herbicides, fungicides'
    },
    # Irrigation & Water
    {
        'name': 'irrigation',
        'display_name': 'Irrigation & Water',
        'icon': 'fas fa-tint',
        'color': 'info',
        'requires_quantity': True,
        'default_unit': 'hours',
        'description': 'Water charges, drip irrigation, sprinkler costs'
    },
    # Land & Field Expenses
    {
        'name': 'land',
        'display_name': 'Land & Field Expenses',
        'icon': 'fas fa-mountain',
        'color': 'secondary',
        'requires_quantity': True,
        'default_unit': 'acres',
        'description': 'Field rent, land preparation, leveling, bunding'
    },
    # Transportation & Logistics
    {
        'name': 'transport',
        'display_name': 'Transportation & Logistics',
        'icon': 'fas fa-truck',
        'color': 'dark',
        'requires_quantity': True,
        'default_unit': 'trips',
        'description': 'Transportation of inputs/outputs, logistics costs'
    },
    # Marketing & Sales
    {
        'name': 'marketing',
        'display_name': 'Marketing & Sales',
        'icon': 'fas fa-chart-line',
        'color': 'success',
        'requires_quantity': False,
        'default_unit': 'units',
        'description': 'Market fees, packaging, storage, commission'
    },
    # Utilities & Services
    {
        'name': 'utilities',
        'display_name': 'Utilities & Services',
        'icon': 'fas fa-plug',
        'color': 'warning',
        'requires_quantity': False,
        'default_unit': 'units',
        'description': 'Electricity, fuel, phone, internet, professional services'
    }
]

# Payment Methods for Indian Farmers
PAYMENT_METHODS = [
    ('Cash', 'Cash'),
    ('UPI', 'UPI'),
    ('Bank Transfer', 'Bank Transfer'),
    ('Cheque', 'Cheque'),
    ('Credit', 'Credit'),
    ('Government Subsidy', 'Government Subsidy')
]

# Indian Farming Seasons
FARMING_SEASONS = [
    ('Kharif', 'Kharif (Monsoon Season)'),
    ('Rabi', 'Rabi (Winter Season)'),
    ('Zaid', 'Zaid (Summer Season)'),
    ('Year-round', 'Year-round Crop')
]

# Common Units for Quantity Tracking
QUANTITY_UNITS = [
    ('kg', 'Kilograms'),
    ('bags', 'Bags'),
    ('liters', 'Liters'),
    ('tons', 'Tons'),
    ('acres', 'Acres'),
    ('hours', 'Hours'),
    ('days', 'Days'),
    ('units', 'Units'),
    ('trips', 'Trips')
]

# Legacy fertilizer categories (for backward compatibility)
FERTILIZER_CATEGORIES = [
    ('Urea', 'Urea'),
    ('DAP', 'DAP (Di-Ammonium Phosphate)'),
    ('NPK', 'NPK Complex'),
    ('MOP', 'MOP (Muriate of Potash)'),
    ('SSP', 'SSP (Single Super Phosphate)'),
    ('Organic', 'Organic Fertilizer'),
    ('Micronutrients', 'Micronutrients'),
    ('Liquid', 'Liquid Fertilizer')
]

# Form for adding a bill with multiple fertilizers
class BillForm(FlaskForm):
    bill_number = StringField('Bill Number (Optional)', validators=[Length(max=50)])
    purchase_date = StringField('Purchase Date', validators=[DataRequired()],
                                render_kw={'type': 'date', 'value': datetime.now().date()})
    submit = SubmitField('Add Bill')

# Form for individual fertilizer items in a bill
class FertilizerItemForm(FlaskForm):
    name = StringField('Fertilizer Name', validators=[DataRequired()])
    category = SelectField('Category', choices=FERTILIZER_CATEGORIES, validators=[DataRequired()])
    price = DecimalField('Price (₹)', validators=[DataRequired(), NumberRange(min=0)])

# Legacy form for backward compatibility
class FertilizerForm(FlaskForm):
    name = StringField('Fertilizer Name', validators=[DataRequired()])
    category = SelectField('Category', choices=FERTILIZER_CATEGORIES, validators=[DataRequired()])
    price = DecimalField('Price (₹)', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Add Fertilizer')

class ImportForm(FlaskForm):
    file = FileField('Import CSV File', validators=[
        DataRequired(),
        FileAllowed(['csv'], 'CSV files only!')
    ])
    submit = SubmitField('Import Data')

# Authentication Forms
class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    farm_name = StringField('Farm Name (Optional)', validators=[Length(max=100)])
    location = StringField('Location (Optional)', validators=[Length(max=100)])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

# Enhanced Forms for Comprehensive Expense Management

class ComprehensiveExpenseForm(FlaskForm):
    """Enhanced expense form with quantity tracking and supplier info"""
    description = StringField('Expense Description', validators=[DataRequired(), Length(max=200)])
    category = SelectField('Category', choices=[], validators=[DataRequired()])
    
    # Quantity and pricing
    quantity = FloatField('Quantity', validators=[Optional(), NumberRange(min=0)])
    unit = SelectField('Unit', choices=QUANTITY_UNITS, validators=[Optional()])
    unit_price = DecimalField('Unit Price (₹)', validators=[Optional(), NumberRange(min=0)], places=2)
    total_amount = DecimalField('Total Amount (₹)', validators=[DataRequired(), NumberRange(min=0)], places=2)
    
    # Relationships
    supplier_id = SelectField('Supplier', choices=[], validators=[Optional()], coerce=lambda x: int(x) if x and x.isdigit() else None)
    field_id = SelectField('Field/Plot', choices=[], validators=[Optional()], coerce=lambda x: int(x) if x and x.isdigit() else None)
    
    # Date and payment info
    expense_date = StringField('Expense Date', validators=[DataRequired()], render_kw={'type': 'date'})
    payment_method = SelectField('Payment Method', choices=PAYMENT_METHODS, validators=[DataRequired()])
    payment_status = SelectField('Payment Status', choices=[('Paid', 'Paid'), ('Pending', 'Pending'), ('Partial', 'Partial')], validators=[DataRequired()])
    
    # Seasonal and crop info
    season = SelectField('Season', choices=FARMING_SEASONS, validators=[Optional()])
    crop_cycle = StringField('Crop/Cycle', validators=[Optional(), Length(max=100)])
    application_date = StringField('Application Date', validators=[Optional()], render_kw={'type': 'date'})
    
    # Notes
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Add Expense')

class BulkExpenseForm(FlaskForm):
    """Form for adding multiple expenses at once"""
    expense_date = StringField('Date for All Items', validators=[DataRequired()], render_kw={'type': 'date'})
    season = SelectField('Season', choices=FARMING_SEASONS, validators=[Optional()])
    crop_cycle = StringField('Crop/Cycle', validators=[Optional(), Length(max=100)])
    field_id = SelectField('Field/Plot', choices=[], validators=[Optional()], coerce=lambda x: int(x) if x and x.isdigit() else None)
    notes = TextAreaField('Common Notes', validators=[Optional(), Length(max=300)])
    submit = SubmitField('Add All Expenses')

class SupplierForm(FlaskForm):
    """Form for managing suppliers"""
    name = StringField('Supplier Name', validators=[DataRequired(), Length(max=100)])
    contact_person = StringField('Contact Person', validators=[Optional(), Length(max=100)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=15)])
    address = TextAreaField('Address', validators=[Optional(), Length(max=300)])
    credit_terms = StringField('Credit Terms', validators=[Optional(), Length(max=100)], render_kw={'placeholder': 'e.g., 30 days, Cash only'})
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=300)])
    submit = SubmitField('Save Supplier')

class FieldForm(FlaskForm):
    """Form for managing fields/plots"""
    name = StringField('Field/Plot Name', validators=[DataRequired(), Length(max=100)])
    area_acres = FloatField('Area (Acres)', validators=[Optional(), NumberRange(min=0)])
    location = StringField('Location', validators=[Optional(), Length(max=200)])
    soil_type = StringField('Soil Type', validators=[Optional(), Length(max=50)])
    crop_cycle = StringField('Current Crop', validators=[Optional(), Length(max=100)])
    season = SelectField('Current Season', choices=FARMING_SEASONS, validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=300)])
    submit = SubmitField('Save Field')

class AIChatForm(FlaskForm):
    """Form for AI chatbot interaction"""
    question = TextAreaField('Ask about farming, expenses, or get advice', 
                           validators=[DataRequired(), Length(max=500)],
                           render_kw={'rows': 3, 'placeholder': 'Ask me about your farm expenses, seasonal planning, cost optimization, or any farming questions...'})
    submit = SubmitField('Get AI Advice')

class ExpenseFilterForm(FlaskForm):
    """Form for filtering and searching expenses"""
    date_from = StringField('From Date', validators=[Optional()], render_kw={'type': 'date'})
    date_to = StringField('To Date', validators=[Optional()], render_kw={'type': 'date'})
    category = SelectField('Category', choices=[('', 'All Categories')], validators=[Optional()])
    supplier_id = SelectField('Supplier', choices=[('', 'All Suppliers')], validators=[Optional()])
    field_id = SelectField('Field', choices=[('', 'All Fields')], validators=[Optional()])
    season = SelectField('Season', choices=[('', 'All Seasons')] + FARMING_SEASONS, validators=[Optional()])
    payment_status = SelectField('Payment Status', choices=[('', 'All Status'), ('Paid', 'Paid'), ('Pending', 'Pending'), ('Partial', 'Partial')], validators=[Optional()])
    submit = SubmitField('Filter')

# Import the Gemini farming assistant
try:
    from gemini_farming_assistant import farming_assistant
except ImportError:
    farming_assistant = None

# Helper functions for the comprehensive system
def init_expense_categories():
    """Initialize comprehensive expense categories in database"""
    with app.app_context():
        for category_data in COMPREHENSIVE_EXPENSE_CATEGORIES:
            existing = ExpenseCategory.query.filter_by(name=category_data['name']).first()
            if not existing:
                category = ExpenseCategory(
                    name=category_data['name'],
                    display_name=category_data['display_name'],
                    icon=category_data['icon'],
                    color=category_data['color'],
                    requires_quantity=category_data['requires_quantity'],
                    default_unit=category_data['default_unit'],
                    description=category_data['description']
                )
                db.session.add(category)
        db.session.commit()

def populate_form_choices(form, user_id):
    """Populate dynamic form choices for suppliers, fields, and categories"""
    # Categories
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    form.category.choices = [(cat.name, cat.display_name) for cat in categories]
    
    # Suppliers
    suppliers = Supplier.query.filter_by(user_id=user_id, is_active=True).all()
    form.supplier_id.choices = [('', 'No Supplier')] + [(s.id, s.name) for s in suppliers]
    
    # Fields
    fields = Field.query.filter_by(user_id=user_id, is_active=True).all()
    form.field_id.choices = [('', 'No Field')] + [(f.id, f.name) for f in fields]

# Create database tables and initialize data
with app.app_context():
    db.create_all()
    # Initialize expense categories
    init_expense_categories()

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user already exists
        email = form.email.data.strip().lower() if form.email.data else ''
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered. Please use a different email or log in.', 'error')
            return render_template('register.html', form=form)
        
        # Create new user
        user = User()
        user.name = form.name.data or ''
        user.email = email
        user.farm_name = form.farm_name.data.strip() if form.farm_name.data else None
        user.location = form.location.data.strip() if form.location.data else None
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in to continue.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower() if form.email.data else ''
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(form.password.data):
            if not user.is_user_active:
                flash('Your account has been deactivated. Please contact the administrator.', 'error')
                return render_template('login.html', form=form)
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password. Please try again.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    user_name = current_user.name
    logout_user()
    flash(f'Goodbye, {user_name}! You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
@active_user_required
def index():
    """Enhanced dashboard with comprehensive expense analytics and AI insights"""
    # Get comprehensive expense data
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.expense_date.desc()).all()
    bills = Bill.query.filter_by(user_id=current_user.id).order_by(Bill.purchase_date.desc()).all()
    
    # Comprehensive statistics
    total_comprehensive_expenses = sum(exp.total_amount for exp in expenses)
    total_bill_expenses = sum(bill.total_amount for bill in bills)
    total_expenses = total_comprehensive_expenses + total_bill_expenses
    
    # Category-wise breakdown
    category_breakdown = {}
    for expense in expenses:
        if expense.category in category_breakdown:
            category_breakdown[expense.category] += expense.total_amount
        else:
            category_breakdown[expense.category] = expense.total_amount
    
    # Add legacy fertilizer data
    for bill in bills:
        if 'fertilizers' in category_breakdown:
            category_breakdown['fertilizers'] += bill.total_amount
        else:
            category_breakdown['fertilizers'] = bill.total_amount
    
    # Field and supplier stats
    user_fields = Field.query.filter_by(user_id=current_user.id, is_active=True).all()
    user_suppliers = Supplier.query.filter_by(user_id=current_user.id, is_active=True).all()
    total_acres = sum(field.area_acres for field in user_fields if field.area_acres)
    cost_per_acre = total_expenses / total_acres if total_acres > 0 else 0
    
    # Recent activities (expenses + bills)
    recent_activities = []
    for expense in expenses[:5]:
        recent_activities.append({
            'type': 'expense',
            'description': expense.description,
            'category': expense.category,
            'amount': expense.total_amount,
            'date': expense.expense_date,
            'quantity_display': expense.quantity_display,
            'supplier': expense.supplier_ref.name if expense.supplier_ref else None
        })
    
    for bill in bills[:3]:
        for fertilizer in bill.fertilizers:
            recent_activities.append({
                'type': 'fertilizer',
                'description': fertilizer.name,
                'category': fertilizer.category,
                'amount': fertilizer.price,
                'date': bill.purchase_date,
                'quantity_display': '',
                'supplier': None
            })
    
    # Sort by date
    recent_activities.sort(key=lambda x: x['date'], reverse=True)
    recent_activities = recent_activities[:8]
    
    # AI Insights (if available)
    ai_insights = None
    if farming_assistant and (expenses or bills):
        try:
            all_user_expenses = expenses
            ai_insights = farming_assistant.analyze_expenses(all_user_expenses, user_fields, current_user)
        except Exception as e:
            print(f"AI insights error: {e}")
    
    # Seasonal analysis
    current_season = 'Kharif' if datetime.now().month in [6, 7, 8, 9, 10] else 'Rabi' if datetime.now().month in [11, 12, 1, 2, 3, 4] else 'Zaid'
    seasonal_expenses = sum(exp.total_amount for exp in expenses if exp.season == current_season)
    
    return render_template('comprehensive_dashboard.html',
                         # Comprehensive data
                         total_expenses=total_expenses,
                         category_breakdown=category_breakdown,
                         recent_activities=recent_activities,
                         
                         # Field and supplier info
                         total_acres=total_acres,
                         cost_per_acre=cost_per_acre,
                         total_fields=len(user_fields),
                         total_suppliers=len(user_suppliers),
                         
                         # Counts
                         total_comprehensive_expenses=len(expenses),
                         total_bills=len(bills),
                         
                         # AI and seasonal
                         ai_insights=ai_insights,
                         current_season=current_season,
                         seasonal_expenses=seasonal_expenses,
                         
                         # Legacy data for backward compatibility
                         bills=bills[:5],
                         expenses=expenses[:5])

@app.route('/add', methods=['GET', 'POST'])
@login_required
@active_user_required
def add_bill():
    """Add a new bill with multiple fertilizers"""
    if request.method == 'POST':
        try:
            # Get form data
            bill_number = request.form.get('bill_number', '').strip()
            purchase_date_str = request.form.get('purchase_date')
            
            # Parse date
            if purchase_date_str:
                purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
            else:
                purchase_date = datetime.now().date()
            
            # Create new bill
            bill = Bill()
            bill.bill_number = bill_number if bill_number else None
            bill.purchase_date = purchase_date
            bill.user_id = current_user.id
            db.session.add(bill)
            db.session.flush()  # Get bill.id
            
            # Process fertilizers
            fertilizer_count = 0
            fertilizer_names = request.form.getlist('fertilizer_name[]')
            fertilizer_categories = request.form.getlist('fertilizer_category[]')
            fertilizer_prices = request.form.getlist('fertilizer_price[]')
            
            for i, name in enumerate(fertilizer_names):
                if name.strip():  # Skip empty entries
                    category = fertilizer_categories[i] if i < len(fertilizer_categories) else 'Urea'
                    price = float(fertilizer_prices[i]) if i < len(fertilizer_prices) and fertilizer_prices[i] else 0.0
                    
                    fertilizer = Fertilizer()
                    fertilizer.name = name.strip()
                    fertilizer.category = category
                    fertilizer.price = price
                    fertilizer.bill_id = bill.id
                    db.session.add(fertilizer)
                    fertilizer_count += 1
            
            # Calculate and save bill total
            bill.calculate_total()
            db.session.commit()
            
            flash(f'Bill added successfully with {fertilizer_count} fertilizers! Total: ₹{bill.total_amount:.2f}', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding bill: {str(e)}', 'error')
    
    return render_template('add_bill.html', 
                         categories=FERTILIZER_CATEGORIES,
                         today_date=datetime.now().date().strftime('%Y-%m-%d'))

# Legacy route for backward compatibility
@app.route('/add_fertilizer', methods=['GET', 'POST'])
@login_required
@active_user_required
def add_fertilizer():
    """Legacy single fertilizer add - creates a bill with one item"""
    form = FertilizerForm()
    if form.validate_on_submit():
        # Create a bill with a single fertilizer
        bill = Bill()
        bill.purchase_date = datetime.now().date()
        bill.user_id = current_user.id
        db.session.add(bill)
        db.session.flush()
        
        fertilizer = Fertilizer()
        fertilizer.name = form.name.data or ''
        fertilizer.category = form.category.data or 'Urea'
        fertilizer.price = float(form.price.data) if form.price.data else 0.0
        fertilizer.bill_id = bill.id
        db.session.add(fertilizer)
        
        bill.calculate_total()
        db.session.commit()
        
        flash('Fertilizer added successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('add_fertilizer.html', form=form)

# Comprehensive Expense Management Routes

@app.route('/expenses/add', methods=['GET', 'POST'])
@login_required
@active_user_required
def add_comprehensive_expense():
    """Add comprehensive expense with quantity tracking and supplier info"""
    form = ComprehensiveExpenseForm()
    populate_form_choices(form, current_user.id)
    
    if form.validate_on_submit():
        try:
            expense = Expense()
            expense.description = form.description.data
            expense.category = form.category.data
            expense.quantity = form.quantity.data
            expense.unit = form.unit.data
            expense.unit_price = form.unit_price.data
            expense.total_amount = form.total_amount.data
            expense.supplier_id = form.supplier_id.data if form.supplier_id.data else None
            expense.field_id = form.field_id.data if form.field_id.data else None
            expense.expense_date = datetime.strptime(form.expense_date.data, '%Y-%m-%d').date()
            expense.payment_method = form.payment_method.data
            expense.payment_status = form.payment_status.data
            expense.season = form.season.data
            expense.crop_cycle = form.crop_cycle.data
            expense.application_date = datetime.strptime(form.application_date.data, '%Y-%m-%d').date() if form.application_date.data else None
            expense.notes = form.notes.data
            expense.user_id = current_user.id
            
            # Set category_id based on name
            category = ExpenseCategory.query.filter_by(name=form.category.data).first()
            if category:
                expense.category_id = category.id
            
            db.session.add(expense)
            db.session.commit()
            
            flash(f'Expense added successfully! {expense.description} - ₹{expense.total_amount:.2f}', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding expense: {str(e)}', 'error')
    
    return render_template('add_comprehensive_expense.html', form=form, today_date=datetime.now().date().strftime('%Y-%m-%d'))

@app.route('/expenses/bulk', methods=['GET', 'POST'])
@login_required
@active_user_required
def add_bulk_expenses():
    """Add multiple expenses in one session"""
    form = BulkExpenseForm()
    populate_form_choices(form, current_user.id)
    
    if request.method == 'POST':
        try:
            base_date = datetime.strptime(form.expense_date.data, '%Y-%m-%d').date()
            season = form.season.data
            crop_cycle = form.crop_cycle.data
            field_id = form.field_id.data if form.field_id.data else None
            notes = form.notes.data
            
            # Process multiple expenses
            descriptions = request.form.getlist('expense_description[]')
            categories = request.form.getlist('expense_category[]')
            quantities = request.form.getlist('expense_quantity[]')
            units = request.form.getlist('expense_unit[]')
            unit_prices = request.form.getlist('expense_unit_price[]')
            totals = request.form.getlist('expense_total[]')
            payment_methods = request.form.getlist('expense_payment_method[]')
            
            expenses_added = 0
            for i, description in enumerate(descriptions):
                if description.strip():
                    expense = Expense()
                    expense.description = description.strip()
                    expense.category = categories[i] if i < len(categories) else 'utilities'
                    expense.quantity = float(quantities[i]) if i < len(quantities) and quantities[i] else None
                    expense.unit = units[i] if i < len(units) else None
                    expense.unit_price = float(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else None
                    expense.total_amount = float(totals[i]) if i < len(totals) and totals[i] else 0.0
                    expense.expense_date = base_date
                    expense.payment_method = payment_methods[i] if i < len(payment_methods) else 'Cash'
                    expense.payment_status = 'Paid'
                    expense.season = season
                    expense.crop_cycle = crop_cycle
                    expense.field_id = field_id
                    expense.notes = notes
                    expense.user_id = current_user.id
                    
                    # Set category_id
                    category = ExpenseCategory.query.filter_by(name=expense.category).first()
                    if category:
                        expense.category_id = category.id
                    
                    db.session.add(expense)
                    expenses_added += 1
            
            db.session.commit()
            flash(f'Successfully added {expenses_added} expenses!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding bulk expenses: {str(e)}', 'error')
    
    # Get categories for template
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    return render_template('add_bulk_expenses.html', form=form, categories=categories, 
                         units=QUANTITY_UNITS, payment_methods=PAYMENT_METHODS)

@app.route('/ai/chat', methods=['GET', 'POST'])
@login_required
@active_user_required
def ai_chat():
    """AI-powered farming assistant chat interface"""
    form = AIChatForm()
    chat_history = session.get('chat_history', [])
    
    if form.validate_on_submit() and farming_assistant:
        try:
            question = form.question.data
            
            # Prepare user context
            expenses = Expense.query.filter_by(user_id=current_user.id).all()
            fields = Field.query.filter_by(user_id=current_user.id).all()
            suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
            
            user_context = f"""
            User: {current_user.name}
            Farm: {current_user.farm_name or 'Not specified'}
            Location: {current_user.location or 'Not specified'}
            Total Expenses: ₹{sum(exp.total_amount for exp in expenses):,.2f}
            Fields: {len(fields)}
            Suppliers: {len(suppliers)}
            """
            
            # Get AI response
            ai_response = farming_assistant.get_farming_advice(question, user_context)
            
            # Add to chat history
            chat_history.append({
                'type': 'user',
                'message': question,
                'timestamp': datetime.now().strftime('%H:%M')
            })
            chat_history.append({
                'type': 'ai',
                'message': ai_response,
                'timestamp': datetime.now().strftime('%H:%M')
            })
            
            # Keep only last 20 messages
            chat_history = chat_history[-20:]
            session['chat_history'] = chat_history
            
            form.question.data = ''  # Clear form
            
        except Exception as e:
            flash(f'AI assistant error: {str(e)}', 'error')
    
    return render_template('ai_chat.html', form=form, chat_history=chat_history)

@app.route('/ai/chat/widget', methods=['POST'])
@login_required
@active_user_required
def ai_chat_widget():
    """AJAX endpoint for floating chat widget"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        if len(question) > 500:
            return jsonify({'error': 'Question too long (max 500 characters)'}), 400
        
        if not farming_assistant:
            return jsonify({'error': 'AI assistant unavailable'}), 503
        
        # Prepare user context
        expenses = Expense.query.filter_by(user_id=current_user.id).all()
        fields = Field.query.filter_by(user_id=current_user.id).all()
        suppliers = Supplier.query.filter_by(user_id=current_user.id).all()
        
        user_context = f"""
        User: {current_user.name}
        Farm: {current_user.farm_name or 'Not specified'}
        Location: {current_user.location or 'Not specified'}
        Total Expenses: ₹{sum(exp.total_amount for exp in expenses):,.2f}
        Fields: {len(fields)}
        Suppliers: {len(suppliers)}
        """
        
        # Get AI response
        ai_response = farming_assistant.get_farming_advice(question, user_context)
        
        # Get current timestamp in Indian timezone
        if farming_assistant:
            current_time = farming_assistant.get_indian_timezone_now()
            timestamp = current_time.strftime('%I:%M %p')
        else:
            timestamp = datetime.now().strftime('%I:%M %p')
        
        # Add to chat history
        chat_history = session.get('chat_history', [])
        chat_history.append({
            'type': 'user',
            'message': question,
            'timestamp': timestamp
        })
        chat_history.append({
            'type': 'ai',
            'message': ai_response,
            'timestamp': timestamp
        })
        
        # Keep only last 20 messages
        chat_history = chat_history[-20:]
        session['chat_history'] = chat_history
        
        return jsonify({
            'success': True,
            'ai_response': ai_response,
            'timestamp': timestamp
        })
        
    except Exception as e:
        return jsonify({'error': f'AI assistant error: {str(e)}'}), 500

@app.route('/ai/chat/history', methods=['GET'])
@login_required
@active_user_required
def get_chat_history():
    """Get chat history for floating widget"""
    chat_history = session.get('chat_history', [])
    return jsonify({'chat_history': chat_history})

@app.route('/ai/chat/clear', methods=['POST'])
@login_required
@active_user_required
def clear_chat_history():
    """Clear chat history"""
    session['chat_history'] = []
    return jsonify({'success': True})

@app.route('/suppliers')
@login_required
@active_user_required
def manage_suppliers():
    """Supplier management interface"""
    suppliers = Supplier.query.filter_by(user_id=current_user.id).order_by(Supplier.name).all()
    return render_template('manage_suppliers.html', suppliers=suppliers)

@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
@active_user_required
def add_supplier():
    """Add new supplier"""
    form = SupplierForm()
    
    if form.validate_on_submit():
        try:
            supplier = Supplier()
            supplier.name = form.name.data
            supplier.contact_person = form.contact_person.data
            supplier.phone = form.phone.data
            supplier.address = form.address.data
            supplier.credit_terms = form.credit_terms.data
            supplier.notes = form.notes.data
            supplier.user_id = current_user.id
            
            db.session.add(supplier)
            db.session.commit()
            
            flash(f'Supplier {supplier.name} added successfully!', 'success')
            return redirect(url_for('manage_suppliers'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding supplier: {str(e)}', 'error')
    
    return render_template('add_supplier.html', form=form)

@app.route('/fields')
@login_required
@active_user_required
def manage_fields():
    """Field/plot management interface"""
    fields = Field.query.filter_by(user_id=current_user.id).order_by(Field.name).all()
    total_acres = sum(field.area_acres for field in fields if field.area_acres)
    return render_template('manage_fields.html', fields=fields, total_acres=total_acres)

@app.route('/fields/add', methods=['GET', 'POST'])
@login_required
@active_user_required
def add_field():
    """Add new field/plot"""
    form = FieldForm()
    
    if form.validate_on_submit():
        try:
            field = Field()
            field.name = form.name.data
            field.area_acres = form.area_acres.data
            field.location = form.location.data
            field.soil_type = form.soil_type.data
            field.crop_cycle = form.crop_cycle.data
            field.season = form.season.data
            field.notes = form.notes.data
            field.user_id = current_user.id
            
            db.session.add(field)
            db.session.commit()
            
            flash(f'Field {field.name} added successfully!', 'success')
            return redirect(url_for('manage_fields'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding field: {str(e)}', 'error')
    
    return render_template('add_field.html', form=form)

@app.route('/export')
@login_required
@active_user_required
def export_data():
    """Export bill and fertilizer data to CSV"""
    bills = Bill.query.filter_by(user_id=current_user.id).order_by(Bill.purchase_date.desc()).all()
    
    # Create CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Purchase Date', 'Bill Number', 'Fertilizer Name', 'Category', 'Price (₹)', 'Bill Total (₹)', 'Items in Bill'])
    
    # Write data
    for bill in bills:
        for fertilizer in bill.fertilizers:
            writer.writerow([
                bill.purchase_date.strftime('%Y-%m-%d'),
                bill.bill_number or f'BILL-{bill.id}',
                fertilizer.name,
                fertilizer.category,
                f'{fertilizer.price:.2f}',
                f'{bill.total_amount:.2f}',
                bill.fertilizer_count
            ])
    
    # Create response
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=fertilizer_expenses_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

@app.route('/import', methods=['GET', 'POST'])
@login_required
@active_user_required
def import_data():
    """Import bill and fertilizer data from CSV"""
    form = ImportForm()
    
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        
        # Read CSV data
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream)
        
        # Skip header row
        next(csv_input, None)
        
        bills_created = 0
        imported_count = 0
        errors = []
        current_bill = None
        current_bill_key = None
        
        for row_num, row in enumerate(csv_input, start=2):
            try:
                if len(row) >= 4:  # At least date, bill_number, name, category, price
                    purchase_date_str = row[0].strip()
                    bill_number = row[1].strip()
                    name = row[2].strip()
                    category = row[3].strip() if row[3].strip() in [choice[0] for choice in FERTILIZER_CATEGORIES] else 'Urea'
                    price = float(row[4].replace('₹', '').replace(',', '').strip()) if len(row) > 4 else 0.0
                    
                    # Parse date
                    try:
                        purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        purchase_date = datetime.now().date()
                    
                    # Create bill key for grouping
                    bill_key = f"{purchase_date}_{bill_number}"
                    
                    # Create new bill if needed
                    if current_bill_key != bill_key:
                        if current_bill:
                            current_bill.calculate_total()
                        
                        current_bill = Bill()
                        current_bill.bill_number = bill_number if bill_number else None
                        current_bill.purchase_date = purchase_date
                        current_bill.user_id = current_user.id
                        db.session.add(current_bill)
                        db.session.flush()
                        bills_created += 1
                        current_bill_key = bill_key
                    
                    # Add fertilizer to current bill
                    if name:
                        fertilizer = Fertilizer()
                        fertilizer.name = name
                        fertilizer.category = category
                        fertilizer.price = price
                        if current_bill and current_bill.id:
                            fertilizer.bill_id = current_bill.id
                        db.session.add(fertilizer)
                        imported_count += 1
                    
            except (ValueError, IndexError) as e:
                errors.append(f'Row {row_num}: {str(e)}')
        
        # Calculate total for last bill
        if current_bill:
            current_bill.calculate_total()
        
        try:
            db.session.commit()
            if bills_created > 0:
                flash(f'Successfully imported {bills_created} bills with {imported_count} fertilizer records!', 'success')
            if errors:
                flash(f'Errors in {len(errors)} rows. Please check your CSV format.', 'warning')
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'error')
        
        return redirect(url_for('index'))
    
    return render_template('import_data.html', form=form)

@app.route('/sample_csv')
def download_sample_csv():
    """Download a sample CSV file for import"""
    sample_data = [
        ['Purchase Date', 'Bill Number', 'Fertilizer Name', 'Category', 'Price (₹)'],
        ['2025-01-15', 'BILL-001', 'Coromandel Urea', 'Urea', '350.00'],
        ['2025-01-15', 'BILL-001', 'IFFCO DAP', 'DAP', '1200.00'],
        ['2025-01-16', 'BILL-002', 'Krishak NPK', 'NPK', '850.00'],
        ['2025-01-16', 'BILL-002', 'MOP Fertilizer', 'MOP', '600.00']
    ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    for row in sample_data:
        writer.writerow(row)
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=sample_fertilizer_import.csv'
    
    return response

# Admin Routes
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard with user management"""
    # Get all users with their stats
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Calculate stats for each user
    user_stats = []
    for user in users:
        bills = Bill.query.filter_by(user_id=user.id).all()
        total_expenses = sum(bill.total_amount for bill in bills)
        total_bills = len(bills)
        total_fertilizers = sum(len([f for f in bill.fertilizers]) for bill in bills)
        
        user_stats.append({
            'user': user,
            'total_expenses': total_expenses,
            'total_bills': total_bills,
            'total_fertilizers': total_fertilizers,
            'last_activity': bills[0].purchase_date if bills else None
        })
    
    # Overall platform statistics
    total_users = len(users)
    active_users = len([u for u in users if u.is_user_active])
    all_bills = Bill.query.all()
    total_platform_expenses = sum(bill.total_amount for bill in all_bills)
    
    return render_template('admin_dashboard.html',
                         user_stats=user_stats,
                         total_users=total_users,
                         active_users=active_users,
                         total_platform_expenses=total_platform_expenses,
                         total_platform_bills=len(all_bills))

@app.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    if current_user.id == user_id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Toggle status
    user.is_user_active = not user.is_user_active
    
    try:
        db.session.commit()
        status = 'activated' if user.is_user_active else 'deactivated'
        flash(f'User {user.name} has been {status} successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating user status: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user_details/<int:user_id>')
@login_required
@admin_required
def admin_user_details(user_id):
    """View detailed user information"""
    user = User.query.get_or_404(user_id)
    bills = Bill.query.filter_by(user_id=user.id).order_by(Bill.purchase_date.desc()).all()
    
    # Calculate detailed statistics
    total_expenses = sum(bill.total_amount for bill in bills)
    all_fertilizers = []
    for bill in bills:
        all_fertilizers.extend([f for f in bill.fertilizers])
    
    fertilizer_categories = Counter([f.category for f in all_fertilizers])
    monthly_expenses = {}
    
    for bill in bills:
        month_key = bill.purchase_date.strftime('%Y-%m')
        if month_key not in monthly_expenses:
            monthly_expenses[month_key] = 0
        monthly_expenses[month_key] += bill.total_amount
    
    return render_template('admin_user_details.html',
                         user=user,
                         bills=bills,
                         total_expenses=total_expenses,
                         total_fertilizers=len(all_fertilizers),
                         fertilizer_categories=dict(fertilizer_categories),
                         monthly_expenses=dict(sorted(monthly_expenses.items(), reverse=True)))

# Force database schema update
with app.app_context():
    try:
        # Check if is_user_active column exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        if 'is_user_active' not in columns:
            # Add the column if it doesn't exist
            db.session.execute(text('ALTER TABLE user ADD COLUMN is_user_active BOOLEAN DEFAULT 1'))
            db.session.commit()
            print('Added is_user_active column to user table')
    except Exception as e:
        print(f'Database update info: {e}')
    
    # Ensure all tables exist
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)