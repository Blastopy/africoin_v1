from flask import render_template, url_for, flash, redirect, request, Flask
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import secrets
from web.data_entry import (RegistrationForms, LoginForm, UpdateProfileForm, ChangePasswordForm, PreferencesForm, ResetPasswordRequestForm, ResetPasswordForm)
from models import User
from web.extensions import db

app = Flask(__name__)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForms()
    if form.validate_on_submit():
        # Generate wallet address
        wallet_address = 'AFC' + secrets.token_hex(20)
        
        # Create user
        user = User(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            country=form.country.data,
            password_hash=generate_password_hash(form.password.data),
            wallet_address=wallet_address,
            created_at=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Check if input is email or username
        user = User.query.filter(
            (User.email == form.email.data) | (User.username == form.email.data)
        ).first()
        
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login unsuccessful. Please check email/username and password.', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    form = UpdateProfileForm()
    password_form = ChangePasswordForm()
    preferences_form = PreferencesForm()
    
    # Populate form data
    form.first_name.data = current_user.first_name
    form.last_name.data = current_user.last_name
    form.username.data = current_user.username
    form.email.data = current_user.email
    form.phone.data = current_user.phone
    form.country.data = current_user.country
    
    # Mock data for demonstration
    recent_transactions = [
        {'date': datetime.utcnow(), 'type': 'received', 'amount': 1.5, 'status': 'confirmed'},
        {'date': datetime.utcnow(), 'type': 'sent', 'amount': 0.5, 'status': 'confirmed'}
    ]
    
    return render_template('profile.html', 
                         form=form, 
                         password_form=password_form,
                         preferences_form=preferences_form,
                         recent_transactions=recent_transactions,
                         exchange_rate=0.25)  # Mock exchange rate

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    form = UpdateProfileForm()
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.phone = form.phone.data
        current_user.country = form.country.data
        
        db.session.commit()
        flash('Your profile has been updated!', 'success')
    
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if check_password_hash(current_user.password_hash, form.current_password.data):
            current_user.password_hash = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash('Your password has been updated!', 'success')
        else:
            flash('Current password is incorrect.', 'danger')
    
    return redirect(url_for('profile'))