# from flask import Blueprint, redirect, render_template, flash, request, session, url_for
# from flask_login import login_required, logout_user, current_user, login_user
# from .auth_forms import LoginForm, SignupForm
# from .auth_models import db, User
# from . import login_manager

# bp = Blueprint('auth', __name__)


# @login_manager.user_loader
# def load_user(user_id):
#     """Check if user is logged-in on every page load."""
#     if user_id is not None:
#         return User.query.get(user_id)
#     return None


# @login_manager.unauthorized_handler
# def unauthorized():
#     """Redirect unauthorized users to Login page."""
#     flash('You must be logged in to view that page.')
#     return redirect(url_for('auth.login'))


# @bp.route('/login', methods=['GET', 'POST'])
# def login():
#     """
#     Log-in page for registered users.

#     GET requests serve Log-in page.
#     POST requests validate and redirect user to dashboard.
#     """
#     # Bypass if user is logged in
#     if current_user.is_authenticated:
#         return redirect(url_for('user.home'))

#     form = LoginForm()
#     # Validate login attempt
#     if form.validate_on_submit():
#         print(form.email.data)
#         user = User.query.filter_by(email=form.email.data).first()
#         if user and user.check_password(password=form.password.data):
#             login_user(user)
#             next_page = request.args.get('next')
#             return redirect(next_page or url_for('home.index'))
#         flash('Invalid username/password combination')
#         return redirect(url_for('auth.login'))
#     return render_template(
#         'auth/login.html',
#         form=form
#     )


# @bp.route('/signup', methods=['GET', 'POST'])
# def signup():
#     """
#     User sign-up page.

#     GET requests serve sign-up page.
#     POST requests validate form & user creation.
#     """
#     form = SignupForm()
#     if form.validate_on_submit():
#         existing_user = User.query.filter_by(email=form.email.data).first()
#         if existing_user is None:
#             user = User(
#                 name=form.name.data,
#                 email=form.email.data,
#             )
#             user.set_password(form.password.data)
#             db.session.add(user)
#             db.session.commit()  # Create new user
#             login_user(user)  # Log in as newly created user
#             print(vars(current_user))
#             flash("Success")
#             return redirect(url_for('home.index'))
#         flash('A user already exists with that email address.')
#     return render_template('auth/register.html',form=form)

# @bp.route("/logout")
# @login_required
# def logout():
#     """User log-out logic."""
#     logout_user()
#     flash("Logged out")
#     return redirect(url_for('auth.login'))