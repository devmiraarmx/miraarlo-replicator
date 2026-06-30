from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models import User


class RegisterForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[
        DataRequired(message='El correo es obligatorio.'),
        Email(message='Ingresa un correo válido.'),
        Length(max=255),
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria.'),
        Length(min=8, message='Mínimo 8 caracteres.'),
    ])
    password_confirm = PasswordField('Confirmar contraseña', validators=[
        DataRequired(message='Confirma tu contraseña.'),
        EqualTo('password', message='Las contraseñas no coinciden.'),
    ])
    submit = SubmitField('Crear cuenta')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('Este correo ya está registrado.')


class LoginForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[
        DataRequired(message='El correo es obligatorio.'),
        Email(message='Ingresa un correo válido.'),
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria.'),
    ])
    remember = BooleanField('Mantener sesión')
    submit = SubmitField('Entrar')
