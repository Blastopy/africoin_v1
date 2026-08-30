from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from flask_login import current_user
from models import User

class RegistrationForms(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired()])
    country = SelectField('Country', choices=[
        ('', 'Select Country'),
        ('NG', 'Nigeria'), ('GH', 'Ghana'), ('KE', 'Kenya'), ('ZA', 'South Africa'),
        ('EG', 'Egypt'), ('ET', 'Ethiopia'), ('TZ', 'Tanzania'), ('UG', 'Uganda'),
        ('CI', 'Ivory Coast'), ('SN', 'Senegal'), ('CM', 'Cameroon'), ('ZW', 'Zimbabwe')
    ], validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password')])
    agree_terms = BooleanField('Agree to Terms', validators=[DataRequired()])
    submit = SubmitField('Create Account')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is already taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already registered. Please use a different one.')

class LoginForm(FlaskForm):
    email = StringField('Email or Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class UpdateProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired()])
    country = SelectField('Country', choices=[
        ('NG', 'Nigeria'), ('GH', 'Ghana'), ('KE', 'Kenya'), ('ZA', 'South Africa'),
        ('EG', 'Egypt'), ('ET', 'Ethiopia'), ('TZ', 'Tanzania'), ('UG', 'Uganda'),
        ('CI', 'Ivory Coast'), ('SN', 'Senegal'), ('CM', 'Cameroon'), ('ZW', 'Zimbabwe')
    ], validators=[DataRequired()])
    submit = SubmitField('Update Profile')

    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('That username is already taken. Please choose a different one.')

    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is already registered. Please use a different one.')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')

class PreferencesForm(FlaskForm):
    language = SelectField('Language', choices=[
        ('en', 'English'), ('fr', 'French'), ('sw', 'Swahili'), ('ar', 'Arabic')
    ])
    currency = SelectField('Currency', choices=[
        ('USD', 'US Dollar'), ('EUR', 'Euro'), ('NGN', 'Nigerian Naira'),
        ('GHS', 'Ghanaian Cedi'), ('KES', 'Kenyan Shilling'), ('ZAR', 'South African Rand')
    ])
    email_notifications = BooleanField('Email Notifications')
    sms_notifications = BooleanField('SMS Notifications')
    submit = SubmitField('Save Preferences')


class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')